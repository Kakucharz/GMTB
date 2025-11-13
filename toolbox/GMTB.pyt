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
        #Param 0: method
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

        #Param 1: input points
        param1 = arcpy.Parameter(
            displayName = "Warstwa punktów wejściowych",
            name = "input_points",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )

        param1.filter.list = ["Point"] #akceptuje tylko warstwy punktowe

        #Param 2: orientation input method
        param2 = arcpy.Parameter(
            displayName = "Sposób wprowadzania orientacji",
            name = "one_point_method",
            datatype = "GPString",
            parameterType = "Optional", #widoczny tylko w metodzie 1P
            direction = "Input"
        )
        param2.filter.type = "ValueList"
        param2.filter.list = ["Manual input", "Choose column"]
        param2.value = param2.filter.list[0]

        #Parametr 1: Kierunek zapadania Dir
        param3 = arcpy.Parameter(
            displayName = "Kierunek zapadania (Dir)",
            name = "dir_value_manual",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )

        #Parametr 1: kąt upadu Dip
        param4 = arcpy.Parameter(
            displayName = "Kąt upadu (Dip)",
            name = "dip_value_manual",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )

        #Param 5: Dir input field
        param5 = arcpy.Parameter(
            displayName = "Dir field",
            name = "dir_field",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input"
        )
        param5.filter.type = "Field"
        param5.parameterDependencies = [param1.name]

        #Param 6: Dip input field
        param6 = arcpy.Parameter(
            displayName = "Dip field",
            name = "dip_field",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input"
        )
        param6.filter.type = "Field"
        param6.parameterDependencies = [param1.name]

        #Promień linii intersekcyjnej
        param7 = arcpy.Parameter(
            displayName = "Rozmiar obszaru analizy [m]",
            name = "analysis_size",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )
        param7.value = 1000 #domyślna wartość

        # Parametr 5: Maksymalna odległość PIONOWA
        param8 = arcpy.Parameter(
            displayName = "Maks. odległość pionowa od terenu [m]",
            name = "vertical_distance",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )
        param8.value = 500 #domyślna wartość

        #Parametr 1: raster NMT
        param9 = arcpy.Parameter(
            displayName = "Numeryczny Model Terenu (NMT)",
            name = "input_nmt_raster",
            datatype = "GPRasterLayer",
            parameterType = "Required",
            direction = "Input"
        )

        #Parametr 2: ścieżka do zapisu wynikowego rastra płaszczyzny
        param10 = arcpy.Parameter(
            displayName = "Wynikowy TIN płaszczyzny geologicznej",
            name = "out_surface_tin",
            datatype = "DETin", 
            parameterType = "Required",
            direction = "Output"
        )

        #Parametr 3: ścieżka do zapisu wynikowej linii intersekcyjnej
        param11 = arcpy.Parameter(
            displayName = "Wynikowa linia intersekcyjna",
            name = "out_intersection_line",
            datatype = "DEFeatureClass",
            parameterType = "Required",
            direction = "Output"
        )

        param2.enabled = param3.enabled = param4.enabled = param5.enabled = param6.enabled = False
        return[param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10, param11]

    def updateParameters(self, parameters):
        """Modyfikuje parametry w zależności od wyboru użytkownika."""

        is_one_point_method = (parameters[0].valueAsText == "Jeden punkt z orientacją")

        # Włączamy lub wyłączamy całą sekcję parametrów dla tej metody
        parameters[2].enabled = is_one_point_method  # Przełącznik Wpisz/Tabela
        
        # Jeśli sekcja jest włączona, uruchamiamy wewnętrzną logikę
        if is_one_point_method:
            sub_method = parameters[2].valueAsText
            
            # Jeśli wybrano "Wpisz ręcznie"
            if sub_method == "Manual input":
                parameters[3].enabled = True  # Pokaż manualny Dir
                parameters[4].enabled = True  # Pokaż manualny Dip
                parameters[5].enabled = False # UKRYJ pole Dir
                parameters[6].enabled = False # UKRYJ pole Dip
            
            # Jeśli wybrano "Odczytaj z tabeli"
            elif sub_method == "Choose column":
                parameters[3].enabled = False # UKRYJ manualny Dir
                parameters[4].enabled = False # UKRYJ manualny Dip
                parameters[5].enabled = True  # Pokaż pole Dir
                parameters[6].enabled = True  # Pokaż pole Dip
        
                if parameters[1].value:
                    try:
                        # Pobieramy ścieżkę do warstwy
                        input_layer_path = parameters[1].valueAsText
                        # Tworzymy listę pól numerycznych ('Long' to 'Integer' w ArcPy)
                        numeric_fields = [f.name for f in arcpy.ListFields(input_layer_path)
                                          if f.type in ['Double', 'Single', 'Integer', 'SmallInteger']]
                        
                        # Wypełniamy nasze "półki" listą "książek"
                        parameters[5].filter.list = numeric_fields
                        parameters[6].filter.list = numeric_fields
                    except Exception:
                        # Jeśli coś pójdzie nie tak (np. zła warstwa), czyścimy listy
                        parameters[5].filter.list = []
                        parameters[6].filter.list = []
                else:
                    # Jeśli użytkownik usunie warstwę, czyścimy listy
                    parameters[5].filter.list = []
                    parameters[6].filter.list = []

        # Jeśli główna metoda jest INNA, upewniamy się, że wszystko jest ukryte
        else:
            parameters[3].enabled = False
            parameters[4].enabled = False
            parameters[5].enabled = False
            parameters[6].enabled = False
        
        
        return


    def updateMessages(self, parameters):
        """Waliduje wartości wprowadzone przez użytkownika i zwraca błędy."""

        # Walidacja pola Dir (parametr 2)
        if parameters[3].enabled and parameters[3].value is not None:
            if not (0 <= parameters[3].value < 360):
                parameters[3].setErrorMessage("Wartość Kierunku (Dir) musi być w zakresie od 0 do 359.")
                
        # Walidacja pola Dip (parametr 3)
        if parameters[4].enabled and parameters[4].value is not None:
            if not (0 <= parameters[4].value <= 90):
                parameters[4].setErrorMessage("Wartość Kąta Upadu (Dip) musi być w zakresie od 0 do 90.")

        return

    def execute(self, parameters, messages):
        method = parameters[0].valueAsText
        input_points = parameters[1].valueAsText
        one_point_method = parameters[2].valueAsText
        dir_degrees = parameters[3].value
        dip_degrees = parameters[4].value
        dir_field = parameters[5].valueAsText
        dip_field = parameters[6].valueAsText
        analysis_size = parameters[7].value
        vertical_distance = parameters[8].value
        input_nmt = parameters[9].valueAsText
        output_surface = parameters[10].valueAsText
        output_intersection = parameters[11].valueAsText
        
        arcpy.env.overwriteOutput = True

        if arcpy.Exists(output_surface): arcpy.management.Delete(output_surface)
        if arcpy.Exists(output_intersection): arcpy.management.Delete(output_intersection)

        if method == "Jeden punkt z orientacją":
            messages.AddMessage("Uruchomiono logikę dla metody: 1 punkt + Dip/Dir")
            
            sub_method = parameters[2].valueAsText
            
            if sub_method == "Manual input":
                messages.AddMessage("Pobieranie orientacji z wartości wpisanych ręcznie...")
                dir_degrees = parameters[3].value
                dip_degrees = parameters[4].value
            
            elif sub_method == "Choose column":
                messages.AddMessage("Pobieranie orientacji z tabeli atrybutów...")
                dir_field = parameters[5].valueAsText
                dip_field = parameters[6].valueAsText
                
                if not dir_field or not dip_field:
                    raise Exception("Proszę wybrać pola z tabeli atrybutów dla wartości Dir i Dip.")
                
                # Używamy SearchCursor do odczytania wartości z pierwszego punktu
                with arcpy.da.SearchCursor(input_points, [dir_field, dip_field]) as cursor:
                    row = next(cursor, None)
                    if row is None:
                        raise Exception("Warstwa wejściowa nie zawiera punktów.")
                    dir_degrees = row[0]
                    dip_degrees = row[1]
                messages.AddMessage(f"Odczytano wartości: Dir = {dir_degrees}, Dip = {dip_degrees}")

            try:
                #ETAP 1: DEFINICJA OBSZARU ANALIZY 
                messages.AddMessage(f"Definiowanie kwadratowego obszaru analizy o boku {analysis_size}m...")
                
                # Używamy pełnego NMT do zdefiniowania układu współrzędnych
                full_nmt_raster = Raster(input_nmt)
                spatial_ref = full_nmt_raster.spatialReference

                # Obliczamy centrum na podstawie punktu wejściowego
                extent = arcpy.Describe(input_points).extent
                center_x = (extent.XMin + extent.XMax) / 2
                center_y = (extent.YMin + extent.YMax) / 2
                
                # Używamy analysis_size dla OBU wymiarów XY 
                half_size = analysis_size / 2
                min_x, max_x = center_x - half_size, center_x + half_size
                min_y, max_y = center_y - half_size, center_y + half_size

                # Tworzymy KWADRATOWY poligon w płaszczyźnie XY
                square_polygon = arcpy.Polygon(arcpy.Array([
                    arcpy.Point(min_x, min_y), arcpy.Point(min_x, max_y),
                    arcpy.Point(max_x, max_y), arcpy.Point(max_x, min_y),
                    arcpy.Point(min_x, min_y)
                ]), spatial_ref)

                #ETAP 2: USTAWIENIE ŚRODOWISKA PRACY
                temp_mask_path = "in_memory/analysis_mask"
                arcpy.management.CopyFeatures(square_polygon, temp_mask_path)
                arcpy.env.extent = square_polygon.extent
                arcpy.env.mask = temp_mask_path
                arcpy.env.cellSize = input_nmt
                arcpy.env.outputCoordinateSystem = spatial_ref
                arcpy.env.snapRaster = input_nmt

                messages.AddMessage("Jawne przycinanie NMT do obszaru analizy...")
                nmt_clipped_raster = arcpy.sa.ExtractByMask(input_nmt, temp_mask_path)
                
                #ETAP 3: OBLICZENIA PŁASZCZYZNY (w ograniczonym zasięgu)
                messages.AddMessage("Obliczanie parametrów płaszczyzny...")
                temp_points_with_z = "in_memory/anchor_point"
                ExtractValuesToPoints(input_points, nmt_clipped_raster, temp_points_with_z, "NONE", "VALUE_ONLY")

                with arcpy.da.SearchCursor(temp_points_with_z, ["SHAPE@X", "SHAPE@Y", "RASTERVALU"]) as cursor:
                    row = next(cursor, None)
                    if row is None: raise Exception("Warstwa wejściowa nie zawiera punktów!")
                    x0, y0, z0 = row[0], row[1], row[2]
                arcpy.management.Delete(temp_points_with_z)
                messages.AddMessage(f"Punkt zakotwiczenia: X={x0}, Y={y0}, Z={z0}")

                # Matematyka płaszczyzny
                dip_rad = math.radians(dip_degrees)
                dir_rad = math.radians(dir_degrees)
                nx = math.sin(dip_rad) * math.sin(dir_rad)
                ny = math.sin(dip_rad) * math.cos(dir_rad)
                nz = math.cos(dip_rad)
                if nz == 0: raise Exception("Płaszczyzny pionowe nie są obecnie wspierane.")

                #ETAP 4: TWORZENIE RASTRA NMT I PŁASZCZYZNY JAKO TABLIC NUMPY
                messages.AddMessage("Tworzenie siatek NumPy dla terenu i płaszczyzny...")
                
                clipped_nmt_obj = Raster(nmt_clipped_raster) 
                lower_left = clipped_nmt_obj.extent.lowerLeft
                rows = clipped_nmt_obj.height
                cols = clipped_nmt_obj.width
                cell_size = clipped_nmt_obj.meanCellWidth
                
                # Generowanie siatek współrzędnych X i Y
                x_coords = np.linspace(lower_left.X, lower_left.X + cell_size * (cols - 1), cols)
                y_coords = np.linspace(lower_left.Y, lower_left.Y + cell_size * (rows - 1), rows)
                x_grid, y_grid = np.meshgrid(x_coords, y_coords)
                y_grid = np.flipud(y_grid) 
                
                # Obliczanie siatki Z dla płaszczyzny geologicznej
                z_grid_geologic = z0 - (nx/nz) * (x_grid - x0) - (ny/nz) * (y_grid - y0)
                z_grid_nmt = arcpy.RasterToNumPyArray(clipped_nmt_obj, nodata_to_value = np.nan)

                #ETAP 5: PRZYCINANIE PIONOWE (filtrowanie według vertical_distance)
                messages.AddMessage(f"Przycinanie płaszczyzny w pionie (max {vertical_distance}m od terenu)...")
                diff_grid = z_grid_geologic - z_grid_nmt
                
                # Ustawiamy NaN dla punktów za daleko od terenu
                z_grid_geologic[np.abs(diff_grid) > vertical_distance] = np.nan
                
                # Ograniczamy zakres Z do przedziału [z0-vertical_distance, z0+vertical_distance]
                z_min_allowed = z0 - vertical_distance
                z_max_allowed = z0 + vertical_distance
                z_grid_geologic[(z_grid_geologic < z_min_allowed) | (z_grid_geologic > z_max_allowed)] = np.nan
                
                messages.AddMessage(f"Zakres Z dla TIN: {z_min_allowed:.1f} - {z_max_allowed:.1f} m n.p.m.")

                #ETAP 6: TWORZENIE LINII INTERSEKCYJNEJ
                messages.AddMessage("Znajdowanie linii intersekcyjnej...")
                
                intersection_raster = arcpy.NumPyArrayToRaster(
                    np.where(np.abs(diff_grid) < 1.0, 1, np.nan), 
                    lower_left, cell_size, cell_size
                )
                intersection_raster_int = arcpy.sa.Int(intersection_raster)
                thinned_raster = arcpy.sa.Thin(intersection_raster_int, "ZERO", "NO_FILTER", "ROUND")
                temp_raw_line = "in_memory/raw_line"
                arcpy.conversion.RasterToPolyline(thinned_raster, temp_raw_line, "ZERO", 0, "NO_SIMPLIFY")
                smoothing_tolerance = cell_size * 5 
                arcpy.cartography.SmoothLine(temp_raw_line, output_intersection, "PAEK", smoothing_tolerance)
                messages.AddMessage(f"Zapisano linię intersekcyjną w: {output_intersection}")
                arcpy.management.Delete(temp_raw_line)

                #ETAP 7: TWORZENIE ZOPTYMALIZOWANEGO TIN (POPRAWIONA LOGIKA!)
                messages.AddMessage("Tworzenie zoptymalizowanej powierzchni TIN...")
                
                # Rzedzenie punktów dla wydajności
                density_multiplier = 10
                points_xyz_sparse = np.vstack([
                    x_grid[::density_multiplier, ::density_multiplier].ravel(),
                    y_grid[::density_multiplier, ::density_multiplier].ravel(),
                    z_grid_geologic[::density_multiplier, ::density_multiplier].ravel()
                ]).T
                
                # Usunięcie punktów z NaN
                points_xyz_sparse = points_xyz_sparse[~np.isnan(points_xyz_sparse).any(axis=1)]
                
                if points_xyz_sparse.shape[0] == 0:
                    raise Exception("Brak punktów do utworzenia TIN-a po filtracji. Zmień parametry.")
                
                messages.AddMessage(f"Liczba punktów dla TIN: {points_xyz_sparse.shape[0]}")

                # Tworzenie warstwy punktowej 3D
                temp_points_for_tin = "in_memory/sparse_points"
                arcpy.management.CreateFeatureclass(
                    "in_memory", "sparse_points", "POINT", 
                    spatial_reference=spatial_ref, has_z="ENABLED"
                )
                
                # Dodaj pole Z_VALUE dla TIN
                arcpy.management.AddField(temp_points_for_tin, "Z_VALUE", "DOUBLE")
                
                with arcpy.da.InsertCursor(temp_points_for_tin, ["SHAPE@XY", "Z_VALUE"]) as cursor:
                    for p in points_xyz_sparse:
                        cursor.insertRow(((p[0], p[1]), p[2]))
                
                tin_input_features = f"{temp_points_for_tin} Z_VALUE Mass_Points"
                arcpy.ddd.CreateTin(output_surface, spatial_ref, tin_input_features)
                messages.AddMessage(f"Utworzono wstępny TIN")
                
                # Przycinanie TIN do kwadratowego obszaru XY
                messages.AddMessage("Przycinanie TIN do prostokątnej obwiedni 2D (X/Y)...")
                
                # Użycie EditTin do przycięcia 
                clip_features = f"{temp_mask_path} <None> Hard_Clip"
                arcpy.ddd.EditTin(output_surface, [clip_features])
                
                messages.AddMessage(f"Zapisano przycięty TIN w: {output_surface}")
                
                # DIAGNOSTYKA: Sprawdź rzeczywisty zasięg TIN
                messages.AddMessage("\n=== RZECZYWISTY ZASIĘG UTWORZONEGO TIN ===")
                tin_desc = arcpy.Describe(output_surface)
                tin_extent = tin_desc.extent
                
                messages.AddMessage(f"Zakres X: {tin_extent.XMin:.2f} - {tin_extent.XMax:.2f} m")
                messages.AddMessage(f"  Szerokość: {tin_extent.XMax - tin_extent.XMin:.2f} m")
                messages.AddMessage(f"Zakres Y: {tin_extent.YMin:.2f} - {tin_extent.YMax:.2f} m")
                messages.AddMessage(f"  Wysokość: {tin_extent.YMax - tin_extent.YMin:.2f} m")
                messages.AddMessage(f"Zakres Z: {tin_extent.ZMin:.2f} - {tin_extent.ZMax:.2f} m n.p.m.")
                messages.AddMessage(f"  Rozpiętość Z: {tin_extent.ZMax - tin_extent.ZMin:.2f} m")
                
                # Podsumowanie
                messages.AddMessage("Zakończono pomyślnie!")
                messages.AddMessage("\n=== PODSUMOWANIE PARAMETRÓW ===")
                messages.AddMessage(f"ZADANE przez użytkownika:")
                messages.AddMessage(f"  - Rozmiar obszaru analizy XY: ±{half_size:.1f} m od punktu")
                messages.AddMessage(f"  - Maks. odległość pionowa: ±{vertical_distance:.1f} m")
                messages.AddMessage(f"  - Oczekiwany zakres Z: {z_min_allowed:.1f} - {z_max_allowed:.1f} m n.p.m.")
                messages.AddMessage(f"\nRZECZYWISTE wymiary TIN:")
                messages.AddMessage(f"  - Szerokość X: {tin_extent.XMax - tin_extent.XMin:.1f} m")
                messages.AddMessage(f"  - Wysokość Y: {tin_extent.YMax - tin_extent.YMin:.1f} m")
                messages.AddMessage(f"  - Rozpiętość Z: {tin_extent.ZMax - tin_extent.ZMin:.1f} m ({tin_extent.ZMin:.1f} - {tin_extent.ZMax:.1f} m n.p.m.)")
                
                # Czyszczenie
                arcpy.management.Delete(temp_points_for_tin)
            
            except Exception as e:
                import traceback
                error_msg = str(e)
                messages.AddError(f"Wystąpił błąd: {error_msg}")
                messages.AddMessage("Szczegóły błędu:")
                tb_lines = traceback.format_exc().split('\n')
                for line in tb_lines:
                    if line.strip():
                        messages.AddMessage(f"  {line}")
                raise
            finally:
                arcpy.ClearEnvironment("extent")
                arcpy.ClearEnvironment("mask")
                if arcpy.Exists("in_memory/analysis_mask"):
                    arcpy.management.Delete("in_memory/analysis_mask")
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

