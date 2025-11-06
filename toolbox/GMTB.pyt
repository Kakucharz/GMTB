# -*- coding: utf-8 -*-

import arcpy
import math
import numpy as np
import timeit

from arcpy.sa import (
    ExtractValuesToPoints,
    Spline,
    Con,
    Raster
)

class Toolbox:
    def __init__(self):
        self.label = "GMTB"
        self.alias = "gmtb"

        self.tools = [GenerujIntersekcje]

class GenerujIntersekcje:
    def __init__(self):
        self.label = "Generuj Linie Intersekcyjne"
        self.description = "Tworzy płaszczyznę geologiczną i znajduje jej przecięcie z NMT"

    def getParameterInfo(self): #parametry narzędzia
        param0 = arcpy.Parameter(
            displayName = "Metoda generowania płaszczyzny",
            name = "method",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input"
        )
        param0.filter.type = "ValueList"
        param0.filter.list = [
            "Jeden punkt z orientacją",
            "Metoda trzech punktów",
            "Wiele punktów (Spline)"
        ]

        param0.value = param0.filter.list[2] #domyślna wartość parametru

        #Parametr 0: punkty od użytkownika
        param1 = arcpy.Parameter(
            displayName = "Warstwa punktów wejściowych",
            name = "input_points",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )

        param1.filter.list = ["Point"] #akceptuje tylko warstwy punktowe

        #Parametr 1: Kierunek zapadania Dir
        param2 = arcpy.Parameter(
            displayName = "Kierunek zapadania (Dir)",
            name = "dir_value",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )

        #Parametr 1: kąt upadu Dip
        param3 = arcpy.Parameter(
            displayName = "Kąt upadu (Dip)",
            name = "dip_value",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )

        #Promień linii intersekcyjnej
        param4 = arcpy.Parameter(
            displayName="Promień linii intersekcyjnej [m]",
            name="horizontal_radius",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input"
        )
        param4.value = 500 #domyślna wartość

        # Parametr 5: Maksymalna odległość PIONOWA
        param5 = arcpy.Parameter(
            displayName="Maks. odległość pionowa od terenu [m]",
            name="vertical_distance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input"
        )
        param5.value = 500 #domyślna wartość

        #Parametr 1: raster NMT
        param6 = arcpy.Parameter(
            displayName = "Numeryczny Model Terenu (NMT)",
            name = "input_nmt_raster",
            datatype = "GPRasterLayer",
            parameterType = "Required",
            direction = "Input"
        )

        #Parametr 2: ścieżka do zapisu wynikowego rastra płaszczyzny
        param7 = arcpy.Parameter(
            displayName="Wynikowy raster płaszczyzny geologicznej",
            name="out_surface_raster",
            datatype="DERasterDataset", 
            parameterType="Required",
            direction="Output"
        )

        #Parametr 3: ścieżka do zapisu wynikowej linii intersekcyjnej
        param8 = arcpy.Parameter(
            displayName = "Wynikowa linia intersekcyjna",
            name = "out_intersection_line",
            datatype = "DEFeatureClass",
            parameterType = "Required",
            direction = "Output"
        )

        return[param0, param1, param2, param3, param4, param5, param6, param7, param8]

    def updateParameters(self, parameters):
        """Modyfikuje parametry w zależności od wyboru użytkownika."""

        if parameters[0].altered:
            wybrana_metoda = parameters[0].valueAsText
            if wybrana_metoda == "Jeden punkt z orientacją":
                parameters[2].enabled = True  # Włącz Dir
                parameters[3].enabled = True  # Włącz Dip
            else:
                parameters[2].enabled = False # Wyłącz Dir
                parameters[3].enabled = False # Wyłącz Dip
                parameters[2].value = None
                parameters[3].value = None        
        return

    def updateMessages(self, parameters):
        """Waliduje wartości wprowadzone przez użytkownika i zwraca błędy."""

        # Walidacja pola Dir (parametr 2)
        if parameters[2].enabled and parameters[2].value is not None:
            if not (0 <= parameters[2].value < 360):
                parameters[2].setErrorMessage("Wartość Kierunku (Dir) musi być w zakresie od 0 do 359.")
                
        # Walidacja pola Dip (parametr 3)
        if parameters[3].enabled and parameters[3].value is not None:
            if not (0 <= parameters[3].value <= 90):
                parameters[3].setErrorMessage("Wartość Kąta Upadu (Dip) musi być w zakresie od 0 do 90.")

        return

    def execute(self, parameters, messages):
        #Odczyt parametrów
        method = parameters[0].valueAsText
        input_points = parameters[1].valueAsText
        dir_degrees = parameters[2].value
        dip_degrees = parameters[3].value
        horizontal_radius = parameters[4].value
        vertical_distance = parameters[5].value
        input_nmt = parameters[6].valueAsText
        output_surface = parameters[7].valueAsText
        output_intersection = parameters[8].valueAsText
        
        #Ustawienie środowiska, żebu rastry działay lepiej
        arcpy.env.extent = input_nmt
        arcpy.env.cellSize = input_nmt
        arcpy.env.overwriteOutput = True #pozwalam na nadpisywanie plików

        #jawne usuwanie plików wyjściowych 
        if arcpy.Exists(output_surface):
            arcpy.management.Delete(output_surface)
        if arcpy.Exists(output_intersection):
            arcpy.management.Delete(output_intersection)

        if method == "Jeden punkt z orientacją":
            messages.AddMessage("Uruchomiono logikę dla metody: 1 punkt + Dip/Dir")
            
            try:
                messages.AddMessage(f"Ograniczenie analizy do {horizontal_radius} m")
                buffer_polygon = "in_memory/analysis_buffer"
                arcpy.analysis.Buffer(input_points, buffer_polygon, horizontal_radius)
                arcpy.env.extent = buffer_polygon
                arcpy.env.mask= buffer_polygon

                #odczytywanie wartości z rastra
                temp_points_with_z = "in_memory/anchor_point"
                messages.AddMessage("Odczytywanie wartości z NMT...")
                arcpy.sa.ExtractValuesToPoints(input_points, input_nmt, temp_points_with_z, "NONE", "VALUE_ONLY")

                with arcpy.da.SearchCursor(temp_points_with_z, ["SHAPE@X", "SHAPE@Y", "RASTERVALU"]) as cursor:
                    row = next(cursor, None)
                    if row is None:
                        raise Exception("Warstwa wejściowa nie zawiera punktów!")
                    x0, y0, z0 = row[0], row[1], row[2]

                arcpy.management.Delete(temp_points_with_z) #sprzątanie po sobie :)
                messages.AddMessage(f"Punkt zakotwiczenia: X= {x0}, Y = {y0}, Z = {z0}")

                #przeliczenie kątów na radiany
                dip_rad = math.radians(dip_degrees)
                dir_rad = math.radians(dir_degrees)

                #obliczenia płaszczyzny A = nx, B = ny, C = nz
                nx = math.sin(dip_rad) * math.sin(dir_rad)
                ny = math.sin(dip_rad) * math.cos(dir_rad)
                nz = math.cos(dip_rad)

                #chwilowa ochrona przed dzieleniem przez 0
                if nz == 0:
                    raise Exception("Płaszczyzny pionowe nie są obecnie wspierane w tej metodzie.")

                messages.AddMessage("Generowanie rastra płaszczyzny...")

                nmt_raster = arcpy.Raster(input_nmt)
                spatial_ref = nmt_raster.spatialReference
                arcpy.env.outputCoordinateSystem = spatial_ref
                lower_left = nmt_raster.extent.lowerLeft
                cell_size = nmt_raster.meanCellWidth
                rows = nmt_raster.height
                cols = nmt_raster.width
                arcpy.env.snapRaster = nmt_raster

                #tablice wsółrzędnych w 1D
                x_coords = np.linspace(
                    lower_left.X + (cell_size / 2),
                    lower_left.X + (cell_size / 2) + (cell_size * (cols - 1)),
                    cols
                )
                y_coords = np.linspace(
                    lower_left.Y + (cell_size / 2),
                    lower_left.Y + (cell_size / 2) + (cell_size * (rows - 1)),
                    rows
                )

                #rozszerzenie z 1D do 2D
                x_grid, y_grid = np.meshgrid(x_coords, y_coords)
                #odwrócenie y_grid, bo jest z jakiegoś powodu odwrócony
                y_grid = np.flipud(y_grid)

                #konwersja z NumPy na ArcPy
                x_raster = arcpy.NumPyArrayToRaster(x_grid, lower_left, cell_size, cell_size)
                y_raster = arcpy.NumPyArrayToRaster(y_grid, lower_left, cell_size, cell_size)

                messages.AddMessage("Zapisywanie rastra płaszczyzny...")
                #równanie płaszczyzny: z = z0 - (nx/nz)*(x - x0) - (ny/nz)*(y - y0)
                geologic_surface = z0 - (nx/nz) * (x_raster - x0) - (ny/nz) * (y_raster - y0)

                messages.AddMessage(f"Przycinanie płaszczyzny do {vertical_distance}m od powierzchni terenu...")
                nmt_in_buffer = Raster(input_nmt)
                diff_raster = geologic_surface - nmt_in_buffer
                clipped_geologic_surface = Con(abs(diff_raster) <= vertical_distance, geologic_surface)
                clipped_geologic_surface.save(output_surface)
                messages.AddMessage(f"Zapisano przycięty raster płaszczyzny w: {output_surface}")

                #tworzenie i zapis linii intersekcyjnej
                messages.AddMessage("Tworzenie linii intersekcyjnej...")
                intersection_raster = arcpy.sa.Con(abs(arcpy.Raster(input_nmt) - geologic_surface) < 1, 1) #tolerancja 1
                
                messages.AddMessage("Konwersja wyniku na warstwę liniową...")
                arcpy.conversion.RasterToPolyline(intersection_raster, output_intersection, "ZERO", 0, "SIMPLIFY")
                messages.AddMessage(f"Zapisano linię intersekcyjną w: {output_intersection}")
                arcpy.management.Delete(buffer_polygon)

                messages.AddMessage("Zakończono pomyślnie!")
            
            except Exception as e:
                messages.AddError(f"Wystąpił błąd: {e}")
                raise

            return
#-----------------------------------------------------------------------------------------------------------------------------------------------
        
        elif method == "Metoda trzech punktów":
            messages.AddMessage("Uruchomiono logikę dla metody: metoda 3 punktów")
            #tutaj kod tworzący to

        elif method == "Wiele punktów (Spline)":
            messages.AddMessage("Uruchomiono logikę dla metody: metoda splajnów dla wielu punktów")

            try:
                #odczytywanie wartości z rastra
                temp_points_with_values = "in_memory/temp_points_extracted"
                messages.AddMessage("Odczytywanie wartości z NMT...")
                arcpy.sa.ExtractValuesToPoints(input_points, input_nmt, temp_points_with_values, "NONE", "VALUE_ONLY")
                #tworzenie płaszczyzny za pomocą splajnów
                messages.AddMessage("Tworzenie gładkiej powierzchni z punktów metodą Spline...")
                tension_weight = 20
                geologic_surface = arcpy.sa.Spline(temp_points_with_values, z_field = "RASTERVALU", spline_type = "TENSION", weight = tension_weight) #używam pola Z do interpolacji
                geologic_surface.save(output_surface)
                messages.AddMessage(f"Zapisano raster płaszczyzny w: {output_surface}")

                #szukanie linii przecięcia
                messages.AddMessage("Tworzenie linii intersekcyjnej...")
                intersection_raster = arcpy.sa.Con(abs(arcpy.Raster(input_nmt) - geologic_surface) <1 ,1) #tolerancja 1

                #konwersja rastra przecięcia na linię
                messages.AddMessage("Konwersja wyniku na warstwę liniową...")
                arcpy.conversion.RasterToPolyline(intersection_raster, output_intersection, "ZERO", 0, "SIMPLIFY")
                messages.AddMessage(f"Zapisano linię intersekcyjną w: {output_intersection}")
                messages.AddMessage("Zakończono pomyślnie!")

            except Exception as e:
                messages.AddError(f"Wystąpił błąd: {e}")
                raise # Rzuć błąd, aby narzędzie zakończyło się jako "nieudane"


            return
        
        return

