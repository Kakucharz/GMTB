# -*- coding: utf-8 -*-

import arcpy
import math
import numpy as np
import timeit
import os

from arcpy.sa import (
    ExtractValuesToPoints,
    Con,
    Raster
)

class Toolbox:
    def __init__(self):
        self.label = "GMTB"
        self.alias = "gmtb"

        self.tools = [GenerujIntersekcje, ObliczMiazszosc, ObliczBladKierunku]

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
            "Metoda trzech punktów"
        ]

        param0.value = param0.filter.list[1] #domyślna wartość parametru

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
        param2.filter.list = ["Wprowadzenie ręczne", "Odczyt z tabeli atrybutów"]
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
            displayName = "Kierunek zapadania (Dir)",
            name = "dir_field",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input"
        )
        param5.filter.type = "Field"
        param5.parameterDependencies = [param1.name]

        #Param 6: Dip input field
        param6 = arcpy.Parameter(
            displayName = "Kąt upadu (Dip)",
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

        #Param 12: add to scene checkbox
        param12 = arcpy.Parameter(
            displayName = "Dodaj wynik do sceny",
            name = "add_to_scene",
            datatype = "GPBoolean",
            parameterType = "Optional",
            direction = "Input"
        )
        param12.value = False

        #Param13: dropdown list with scenes
        param13 = arcpy.Parameter(
            displayName = "Wybierz scenę",
            name = "target_scene",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input"
        )
        param13.filter.type = "ValueList"
        param13.enabled = False

        param2.enabled = param3.enabled = param4.enabled = param5.enabled = param6.enabled = False
        return[param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10, param11, param12, param13]

    def updateParameters(self, parameters):
        """Modyfikuje parametry w zależności od wyboru użytkownika."""

        is_one_point_method = (parameters[0].valueAsText == "Jeden punkt z orientacją")

        # Włączamy lub wyłączamy całą sekcję parametrów dla tej metody
        parameters[2].enabled = is_one_point_method  # Przełącznik Wpisz/Tabela
        
        # Jeśli sekcja jest włączona, uruchamiamy wewnętrzną logikę
        if is_one_point_method:
            sub_method = parameters[2].valueAsText
            
            # Jeśli wybrano "Wpisz ręcznie"
            if sub_method == "Wprowadzenie ręczne":
                parameters[3].enabled = True  # Pokaż manualny Dir
                parameters[4].enabled = True  # Pokaż manualny Dip
                parameters[5].enabled = False # UKRYJ pole Dir
                parameters[6].enabled = False # UKRYJ pole Dip
            
            # Jeśli wybrano "Odczyt z tabeli atrybutów"
            elif sub_method == "Odczyt z tabeli atrybutów":
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
                        
                        parameters[5].filter.list = numeric_fields
                        parameters[6].filter.list = numeric_fields
                    except Exception:
                        # Czyszczenie list w przypadku błędu
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

        #Sprawdzenie stanu checkboxa
        if parameters[12].value == True:
            parameters[13].enabled = True

            #Wypełnienia listy nazwami scen w projekcie
            try:
                aprx = arcpy.mp.ArcGISProject("CURRENT")
                scene_names = [m.name for m in aprx.listMaps() if m.mapType == "SCENE"]
                parameters[13].filter.list = scene_names
            except Exception:
                #jak nie ma scen to lista będzie pusta
                parameters[13].filter.list = []
        else:
            #jeżeli odznaczymy to czyścimy listę scen
            parameters[13].enabled = False
            parameters[13].value = None

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
        # --- ETAP 0: Pobieranie parametrów i przygotowanie środowiska ---
        method = parameters[0].valueAsText
        input_points = parameters[1].valueAsText
        sub_method = parameters[2].valueAsText
        analysis_size = parameters[7].value
        vertical_distance = parameters[8].value
        input_nmt = parameters[9].valueAsText
        output_surface = parameters[10].valueAsText
        output_intersection = parameters[11].valueAsText
        add_to_scene = parameters[12].value
        target_scene_name = parameters[13].valueAsText
        
        arcpy.env.overwriteOutput = True
        if arcpy.Exists(output_surface): arcpy.management.Delete(output_surface)
        if arcpy.Exists(output_intersection): arcpy.management.Delete(output_intersection)


        try:
            # Inicjalizacja kluczowych zmiennych 
            nx, ny, nz, x0, y0, z0, center_x, center_y = [None] * 8
            dip_degrees_for_output, dir_degrees_for_output = None, None

            #CZĘŚĆ 1: UNIKALNE OBLICZENIA (przygotowanie parametrów płaszczyzny dla obu metod)
            
            if method == "Jeden punkt z orientacją":
                messages.AddMessage("Metoda 1-punktowa: Obliczanie parametrów płaszczyzny...")
                if sub_method == "Wprowadzenie ręczne":
                    dir_degrees, dip_degrees = parameters[3].value, parameters[4].value
                else:
                    dir_field, dip_field = parameters[5].valueAsText, parameters[6].valueAsText
                    with arcpy.da.SearchCursor(input_points, [dir_field, dip_field]) as cursor:
                        row = next(cursor, None); dir_degrees, dip_degrees = float(row[0]), float(row[1])
                dip_degrees_for_output, dir_degrees_for_output = dip_degrees, dir_degrees
                
                #pobieram współrzędne punktu zakotwiczenia
                temp_point_z = "in_memory/anchor_point"
                arcpy.sa.ExtractValuesToPoints(input_points, input_nmt, temp_point_z, "NONE", "VALUE_ONLY")
                with arcpy.da.SearchCursor(temp_point_z, ["SHAPE@X", "SHAPE@Y", "RASTERVALU"]) as cursor:
                    row = next(cursor, None)
                    if row is None or row[2] is None or row[2] < -1e38: raise Exception("Punkt wejściowy poza zasięgiem NMT.")
                    x0, y0, z0 = row[0], row[1], row[2]
                arcpy.management.Delete(temp_point_z)
                
                #zamiana Dip/Dir na wektor normalny (nx, ny, nz) za pomocą trygonometrii
                dip_rad, dir_rad = math.radians(dip_degrees), math.radians(dir_degrees)
                nx, ny, nz = math.sin(dip_rad) * math.sin(dir_rad), math.sin(dip_rad) * math.cos(dir_rad), math.cos(dip_rad)
                extent = arcpy.Describe(input_points).extent
                center_x, center_y = (extent.XMin + extent.XMax) / 2, (extent.YMin + extent.YMax) / 2

            elif method == "Metoda trzech punktów":
                messages.AddMessage("Metoda 3-punktowa: Obliczanie parametrów płaszczyzny...")
                if int(arcpy.management.GetCount(input_points)[0]) != 3: raise Exception("Wymagane 3 punkty.")
                
                points_3d_temp = "in_memory/points_with_z"; arcpy.sa.ExtractValuesToPoints(input_points, input_nmt, points_3d_temp)
                coords = [row for row in arcpy.da.SearchCursor(points_3d_temp, ["SHAPE@X", "SHAPE@Y", "RASTERVALU"])]; arcpy.management.Delete(points_3d_temp)
                (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = coords[0], coords[1], coords[2]
                
                #zamiana 3 punkty na wektor normalny (nx, ny, nz) za pomocą iloczynu wektorowego
                nx, ny, nz = (y1-y2)*(z3-z2)-(y3-y2)*(z1-z2), -((x1-x2)*(z3-z2)-(x3-x2)*(z1-z2)), (x1-x2)*(y3-y2)-(x3-x2)*(y1-y2)
                x0, y0, z0 = x2, y2, z2
                center_x, center_y = (x1+x2+x3)/3, (y1+y2+y3)/3

            if nz == 0: raise Exception("Płaszczyzna jest pionowa. Ta metoda nie jest obecnie wspierana.")

            #CZĘŚĆ 2: WSPÓLNY POTOK PRZETWARZANIA
            messages.AddMessage("Rozpoczynanie wspólnego potoku przetwarzania...")
            
            #ETAP W1: Definicja obszaru i środowiska
            spatial_ref = arcpy.Describe(input_nmt).spatialReference
            half_size = analysis_size / 2
            min_x, max_x, min_y, max_y = center_x-half_size, center_x+half_size, center_y-half_size, center_y+half_size
            square_polygon = arcpy.Polygon(arcpy.Array([arcpy.Point(min_x, min_y), arcpy.Point(min_x, max_y), arcpy.Point(max_x, max_y), arcpy.Point(max_x, min_y)]), spatial_ref)
            temp_mask_path = "in_memory/analysis_mask"
            arcpy.management.CopyFeatures(square_polygon, temp_mask_path)
            arcpy.env.extent, arcpy.env.mask, arcpy.env.cellSize, arcpy.env.outputCoordinateSystem, arcpy.env.snapRaster = square_polygon.extent, temp_mask_path, input_nmt, spatial_ref, input_nmt

            #ETAP W2: Tworzenie siatek NumPy
            messages.AddMessage("Tworzenie siatek NumPy...")
            nmt_clipped_raster = arcpy.sa.ExtractByMask(input_nmt, temp_mask_path)
            clipped_nmt_obj = Raster(nmt_clipped_raster)
            lower_left, rows, cols, cell_size = clipped_nmt_obj.extent.lowerLeft, clipped_nmt_obj.height, clipped_nmt_obj.width, clipped_nmt_obj.meanCellWidth
            x_coords = np.linspace(lower_left.X, lower_left.X + cell_size * (cols - 1), cols)
            y_coords = np.linspace(lower_left.Y, lower_left.Y + cell_size * (rows - 1), rows)
            x_grid, y_grid = np.meshgrid(x_coords, y_coords); y_grid = np.flipud(y_grid)
            z_grid_geologic = z0 - (nx/nz) * (x_grid - x0) - (ny/nz) * (y_grid - y0)
            z_grid_nmt = arcpy.RasterToNumPyArray(clipped_nmt_obj, nodata_to_value=np.nan)

            #ETAP W3: Przycinanie pionowe i tworzenie linii intersekcyjnej
            messages.AddMessage("Przycinanie i znajdowanie intersekcji...")
            diff_grid = z_grid_geologic - z_grid_nmt

            # Ustawiamy NaN dla punktów za daleko od terenu
            z_grid_geologic[np.abs(diff_grid) > vertical_distance] = np.nan

            # Ograniczamy zakres Z do przedziału [z0-vertical_distance, z0+vertical_distance]
            z_min_allowed, z_max_allowed = z0 - vertical_distance, z0 + vertical_distance
            z_grid_geologic[(z_grid_geologic < z_min_allowed) | (z_grid_geologic > z_max_allowed)] = np.nan

            #tworzenie linii intersekcyjnej
            intersection_raster = arcpy.NumPyArrayToRaster(np.where(np.abs(diff_grid) < 1.0, 1, np.nan), lower_left, cell_size, cell_size)
            thinned_raster = arcpy.sa.Thin(arcpy.sa.Int(intersection_raster), "ZERO", "NO_FILTER", "ROUND")
            temp_raw_line = "in_memory/raw_line"
            arcpy.conversion.RasterToPolyline(thinned_raster, temp_raw_line, "ZERO", 0, "NO_SIMPLIFY")
            arcpy.cartography.SmoothLine(temp_raw_line, output_intersection, "PAEK", cell_size * 5)
            arcpy.management.Delete(temp_raw_line); messages.AddMessage(f"Zapisano linię intersekcyjną w: {output_intersection}")

            #ETAP W4: Tworzenie TIN
            messages.AddMessage("Tworzenie powierzchni TIN...")

            #przerzedzenie punktów dla wydajności
            density_multiplier = 10
            points_xyz_sparse = np.vstack([
                    x_grid[::density_multiplier, ::density_multiplier].ravel(),
                    y_grid[::density_multiplier, ::density_multiplier].ravel(),
                    z_grid_geologic[::density_multiplier, ::density_multiplier].ravel()
            ]).T

            #usunięcie punktów z NaN
            points_xyz_sparse = points_xyz_sparse[~np.isnan(points_xyz_sparse).any(axis=1)]
            if points_xyz_sparse.shape[0] == 0: raise Exception("Brak punktów do utworzenia TIN.")

            #tworzenie warstwy punktowej 3D
            temp_points_for_tin = "in_memory/sparse_points"
            arcpy.management.CreateFeatureclass("in_memory", "sparse_points", "POINT", spatial_reference=spatial_ref, has_z="ENABLED")

            #dodaj pole Z_VALUE dla TIN
            arcpy.management.AddField(temp_points_for_tin, "Z_VALUE", "DOUBLE")

            with arcpy.da.InsertCursor(temp_points_for_tin, ["SHAPE@XY", "Z_VALUE"]) as cursor:
                for p in points_xyz_sparse: cursor.insertRow(((p[0], p[1]), p[2]))

            arcpy.ddd.CreateTin(output_surface, spatial_ref, f"{temp_points_for_tin} Z_VALUE Mass_Points")
            arcpy.ddd.EditTin(output_surface, [f"{temp_mask_path} <None> Hard_Clip"])
            arcpy.management.Delete(temp_points_for_tin); messages.AddMessage(f"Zapisano TIN w: {output_surface}")

            #ETAP W5: Dodawanie wyników na mapę i zapis atrybutów
            aprx = arcpy.mp.ArcGISProject("CURRENT"); map_2d_to_add_to = None

            if aprx.activeMap and aprx.activeMap.mapType == "MAP": map_2d_to_add_to = aprx.activeMap
            else:
                map_list_2d = [m for m in aprx.listMaps() if m.mapType == "MAP"]
                if map_list_2d: map_2d_to_add_to = map_list_2d[0]
            if map_2d_to_add_to: map_2d_to_add_to.addDataFromPath(output_intersection)
            if add_to_scene and target_scene_name:
                scene = next((m for m in aprx.listMaps() if m.mapType == "SCENE" and m.name == target_scene_name), None)
                if scene: scene.addDataFromPath(output_surface); scene.addDataFromPath(output_intersection)

            #rozróżniona logika dodawania dip i dir do tabeli atrybutów
            if dip_degrees_for_output is not None:
                arcpy.management.AddField(output_intersection, "Dip", "DOUBLE", field_alias="DIP")
                arcpy.management.AddField(output_intersection, "Dir", "DOUBLE", field_alias="DIR")
                with arcpy.da.UpdateCursor(output_intersection, ["Dip", "Dir"]) as cursor:
                    for row in cursor: cursor.updateRow([dip_degrees_for_output, dir_degrees_for_output])
            
            elif method == "Metoda trzech punktów":
                mag_xy = math.sqrt(nx**2 + ny**2); mag_xyz = math.sqrt(nx**2 + ny**2 + nz**2)
                dip_val = math.degrees(math.asin(mag_xy / mag_xyz)); dir_val = math.degrees(math.atan2(nx, ny))
                if dir_val < 0: dir_val += 360
                arcpy.management.AddField(output_intersection, "Dip", "DOUBLE", field_alias="DIP")
                arcpy.management.AddField(output_intersection, "Dir", "DOUBLE", field_alias="DIR")
                with arcpy.da.UpdateCursor(output_intersection, ["Dip", "Dir"]) as cursor:
                    for row in cursor: cursor.updateRow([dip_val, dir_val])

            messages.AddMessage("\nZakończono pomyślnie!")

        except Exception as e:
            import traceback
            error_msg = str(e)
            messages.AddError(f"Wystąpił błąd: {error_msg}")
            tb_lines = traceback.format_exc().split('\n')
            for line in tb_lines:
                if line.strip(): messages.AddMessage(f"  {line}")
            raise
        finally:
            arcpy.ClearEnvironment("extent")
            arcpy.ClearEnvironment("mask")
            if arcpy.Exists("in_memory/analysis_mask"):
                arcpy.management.Delete("in_memory/analysis_mask")
        
        return

class ObliczMiazszosc:
    def __init__(self):
        self.label = "Oblicz Miąższość"
        self.description = "Oblicza miąższość pozorną i rzeczywistą na podstawie dwóch linii intersekcyjnych i kąta zapadania"

    def getParameterInfo(self):
        #Param 0: metoda obliczeń
        param0 = arcpy.Parameter(
        displayName="Metoda obliczeń",
        name="method",
        datatype="GPString",
        parameterType="Required",
        direction="Input"
        )
        param0.filter.type = "ValueList"
        param0.filter.list = ["Lokalna (w punkcie)", "Globalna (pesymistyczna)", "Globalna (optymistyczna)"]
        param0.value = param0.filter.list[0]

        #Param 1: linia 1
        param1 = arcpy.Parameter(
            displayName = "Pierwsza linia intersekcyjna",
            name = "in_line_1",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )
        param1.filter.list = ["Polyline"]

        #Param 2: linia 2
        param2 = arcpy.Parameter(
            displayName = "Druga linia intersekcyjna",
            name = "in_line_2",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )
        param2.filter.list = ["Polyline"]

        #Param 3: point
        param3 = arcpy.Parameter(
            displayName = "Punkt pomiaru",
            name = "in_point",
            datatype = "GPFeatureLayer",
            parameterType = "Optional",
            direction = "Input"
        )
        param3.filter.list = ["Point"]

        #Param 4: Dip input method
        param4 = arcpy.Parameter(
            displayName = "Sposób wprowadzania kąta zapadania",
            name = "dip_input_method",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input"
        )
        param4.filter.type = "ValueList"
        param4.filter.list = ["Wprowadzenie ręczne", "Odczyt z Linii 1"]
        param4.value = param4.filter.list[0]

        #Param 5: Kąt zapadania (DIP)
        param5 = arcpy.Parameter(
            displayName = "Kąt zapadania warstwy (dip)",
            name = "dip_angle",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )

        #Param 6: wybór pola dla kąta
        param6 = arcpy.Parameter(
            displayName = "Pole z wartością kąta (Dip)",
            name = "dip_field",
            datatype = "GPString",
            parameterType ="Optional",
            direction = "Input"
        )
        param6.filter.type = "Field"
        # Ten parametr zależy od 'Linii 1' (param1)
        param6.parameterDependencies = [param1.name] 

        #Param 7: output line
        param7 = arcpy.Parameter(
            displayName = "Wynikowa linia pomiaru miąższości",
            name = "out_measurement_line",
            datatype = "DEFeatureClass",
            parameterType = "Required",
            direction = "Output"
        )

        return [param0, param1, param2, param3, param4, param5, param6, param7]

    def updateParameters(self, parameters):
        # Pokaż/ukryj parametr punktu w zależności od wybranej metody
        if parameters[0].value == "Lokalna (w punkcie)":
            parameters[3].enabled = True
            parameters[3].parameterType = "Required" # Staje się wymagany
        else:
            parameters[3].enabled = False
            parameters[3].parameterType = "Optional" # Musi być opcjonalny, gdy ukryty

        # Widocznoać pola kąt
        dip_method = parameters[4].value
        if dip_method == "Wprowadzenie ręczne":
            parameters[5].enabled = True
            parameters[5].parameterType = "Required"
        else: 
            parameters[5].enabled = False
            parameters[5].parameterType = "Optional"

        dip_method = parameters[4].value
        manual_dip_param = parameters[5]
        field_dip_param = parameters[6] 

        if dip_method == "Wprowadzenie ręczne":
            manual_dip_param.enabled = True
            manual_dip_param.parameterType = "Required"
            field_dip_param.enabled = False
            field_dip_param.parameterType = "Optional"
        
        else:
            manual_dip_param.enabled = False
            manual_dip_param.parameterType = "Optional"
            field_dip_param.enabled = True
            field_dip_param.parameterType = "Required"
            
            # Wypełnij listę polami numerycznymi z 'Linii 1'
            in_line_1_param = parameters[1]
            if in_line_1_param.value:
                try:
                    numeric_fields = [f.name for f in arcpy.ListFields(in_line_1_param.valueAsText)
                                    if f.type in ['Double', 'Single', 'Integer', 'SmallInteger']]
                    field_dip_param.filter.list = numeric_fields
                except Exception:
                    field_dip_param.filter.list = []
            else:
                field_dip_param.filter.list = []
        
        # Walidacja kąta
        if parameters[5].value is not None:
            if not (0 < parameters[5].value < 90):
                parameters[5].setErrorMessage(...)

        return
    
    def updateMessages(self, parameters):
        #Walidacja wartości kąta zapadania
        if parameters[5].value is not None:
            if not ( 0 < parameters[5].value <= 90):
                parameters[5].setErrorMessage("Kąt zapadania (Dip) musi być w zakresie (0, 90].")
        return

    def execute(self, parameters, messages):
        method = parameters[0].valueAsText
        in_line_1 = parameters[1].valueAsText
        in_line_2 = parameters[2].valueAsText
        in_point = parameters[3].valueAsText
        dip_input_method = parameters[4].valueAsText
        dip_angle_manual = parameters[5].value
        dip_field_name = parameters[6].valueAsText
        out_line = parameters[7].valueAsText

        arcpy.env.overwriteOutput = True

        try:
            #wybór metody odczytu kąta
            dip_angle = None
            if dip_input_method == "Wprowadzenie ręczne":
                dip_angle = dip_angle_manual
                if dip_angle is None:
                    raise ValueError("Nie wprowadzono wartości dla kąta zapadania.")
                messages.AddMessage(f"Użyto ręcznie wprowadzonego kąta zapadania: {dip_angle}°")
            
            else:
                messages.AddMessage(f"Próba automatycznego odczytania kąta zapadania z pola '{dip_field_name}'...")
                
                # Sprawdź, czy użytkownik wybrał pole
                if not dip_field_name:
                    raise ValueError("Nie wybrano pola z tabeli atrybutów dla wartości Dip.")
                
                # Odczytaj wartość z wybranego pola
                with arcpy.da.SearchCursor(in_line_1, [dip_field_name]) as cursor:
                    row = next(cursor, None)
                    if row is None: raise Exception("Warstwa 'Linia 1' jest pusta. Nie można odczytać kąta.")
                    if row[0] is None: raise Exception(f"Wartość w polu '{dip_field_name}' jest pusta (Null).")
                    
                    dip_angle = float(row[0])
                    messages.AddMessage(f"Pomyślnie odczytano kąt zapadania: {dip_angle}°")

            # Walidacja odczytanego/wpisanego kąta
            if not (0 < dip_angle <= 90):
                raise ValueError(f"Kąt zapadania ({dip_angle}°) jest poza prawidłowym zakresem (0, 90].")

            # Inicjalizacja zmiennych, które zostaną wypełnione w zależności od metody
            apparent_thickness = None
            start_point_coords = None
            end_point_coords = None
            spatial_ref = arcpy.Describe(in_line_1).spatialReference

            #CZĘŚĆ 1: Wyznaczenie miąższości pozornej zgodnie z wybraną metodą
            if method == "Lokalna (w punkcie)":
                messages.AddMessage("Uruchomiono metodę lokalną...")
                
                # Znalezienie punktu na Linii 1
                arcpy.analysis.Near(in_point, in_line_1, location=True)
                with arcpy.da.SearchCursor(in_point, ["NEAR_X", "NEAR_Y"]) as cursor:
                    row = next(cursor, None)
                    if row and row[0] != -1:
                        start_point_coords = (row[0], row[1])
                if not start_point_coords:
                    raise Exception("Nie udało się zlokalizować punktu na pierwszej linii intersekcyjnej.")

                # Pomiar do Linii 2
                temp_start_point = arcpy.management.CreateFeatureclass("in_memory", "start_point", "POINT", spatial_reference=spatial_ref)[0]
                with arcpy.da.InsertCursor(temp_start_point, ["SHAPE@XY"]) as cursor:
                    cursor.insertRow([start_point_coords])
                
                arcpy.analysis.Near(temp_start_point, in_line_2, location=True)
                
                with arcpy.da.SearchCursor(temp_start_point, ["NEAR_DIST", "NEAR_X", "NEAR_Y"]) as cursor:
                    row = next(cursor, None)
                    if row and row[0] != -1:
                        apparent_thickness = row[0]
                        end_point_coords = (row[1], row[2])
                
                arcpy.management.Delete(temp_start_point)
                if apparent_thickness is None:
                    raise Exception("Nie udało się znaleźć punktu na drugiej linii intersekcyjnej.")
                
                messages.AddMessage(f"ZNALEZIONO MIĄŻSZOŚĆ POZORNĄ: {apparent_thickness:.2f} m")

            elif method in ["Globalna (pesymistyczna)", "Globalna (optymistyczna)"]:
                messages.AddMessage(f"Uruchomiono metodę globalną: {method}")
                
                # Dyskretyzacja
                temp_points = "in_memory/densified_points"
                arcpy.management.GeneratePointsAlongLines(in_line_1, temp_points, "DISTANCE", Distance="1 Meters")
                
                # Analiza Near
                arcpy.analysis.Near(temp_points, in_line_2, location=True, angle=True)
                
                # Zebranie wyników i wybór
                if method == "Globalna (pesymistyczna)":
                    # Logika dla pesymistycznej: szukamy absolutnego minimum
                    results = {}
                    with arcpy.da.SearchCursor(temp_points, ["SHAPE@X", "SHAPE@Y", "NEAR_DIST", "NEAR_X", "NEAR_Y"]) as cursor:
                        for row in cursor:
                            dist = row[2]
                            if dist != -1:
                                results[dist] = ((row[0], row[1]), (row[3], row[4]))
                    if not results:
                        raise Exception("Nie udało się znaleźć żadnej odległości między liniami.")

                    all_distances = list(results.keys())
                    if all_distances:
                        average_apparent = sum(all_distances) / len(all_distances)
                        dip_rad = math.radians(dip_angle)
                        average_real = average_apparent * math.sin(dip_rad)
                        
                        messages.AddMessage("--- Statystyki Globalne ---")
                        messages.AddMessage(f"Średnia miąższość pozorna: {average_apparent:.2f} m")
                        messages.AddMessage(f"Średnia miąższość rzeczywista: {average_real:.2f} m")
                        messages.AddMessage("--------------------------")
                    
                    target_distance = min(results.keys())
                    messages.AddMessage(f"Znaleziono najkrótszą odległość (pesymistyczna): {target_distance:.2f} m")
                    start_point_coords, end_point_coords = results[target_distance]
                    apparent_thickness = target_distance

                else: #logika dla optymistycznej
                    messages.AddMessage("Filtrowanie wyników w poszukiwaniu najdłuższego prostopadłego odcinka...")
                    
                    # 1. Oblicz ogólny kierunek linii
                    with arcpy.da.SearchCursor(in_line_1, ["SHAPE@"]) as cursor:
                        line_geom = next(cursor)[0]
                        p_start, p_end = line_geom.firstPoint, line_geom.lastPoint
                        general_angle_rad = math.atan2(p_end.Y - p_start.Y, p_end.X - p_start.X)
                        general_angle_deg = math.degrees(general_angle_rad)

                    # 2. Oblicz idealne kąty prostopadłe (w obu kierunkach)
                    perpendicular_angle_1 = (general_angle_deg + 90)
                    # Normalizacja, aby kąt był w zakresie 0-360!
                    if perpendicular_angle_1 < 0: perpendicular_angle_1 += 360
                    perpendicular_angle_2 = (perpendicular_angle_1 + 180) % 360
                    
                    messages.AddMessage(f"Wykryto ogólny kierunek warstw: {general_angle_deg:.1f}°. Oczekiwane kąty pomiaru: {perpendicular_angle_1:.1f}° lub {perpendicular_angle_2:.1f}°")
                    
                    # 3. Filtruj wyniki i znajdź najlepszy
                    angle_tolerance = 20
                    filtered_results = []
                    
                    with arcpy.da.SearchCursor(temp_points, ["SHAPE@X", "SHAPE@Y", "NEAR_DIST", "NEAR_X", "NEAR_Y", "NEAR_ANGLE"]) as cursor:
                        for row in cursor:
                            dist, near_angle = row[2], row[5]
                            if dist != -1:
                                #Sprawdzamy oba możliwe kąty prostopadłe
                                angle_diff1 = abs(near_angle - perpendicular_angle_1)
                                if angle_diff1 > 180: angle_diff1 = 360 - angle_diff1

                                angle_diff2 = abs(near_angle - perpendicular_angle_2)
                                if angle_diff2 > 180: angle_diff2 = 360 - angle_diff2
                                
                                # Jeśli którykolwiek z kątów pasuje, akceptujemy wynik
                                if min(angle_diff1, angle_diff2) <= angle_tolerance:
                                    start_xy = (row[0], row[1])
                                    end_xy = (row[3], row[4])
                                    filtered_results.append((dist, start_xy, end_xy))

                    if not filtered_results:
                        raise Exception(f"Nie znaleziono żadnego odcinka pomiarowego w tolerancji kątowej {angle_tolerance}°. Spróbuj z innymi danymi lub zwiększ tolerancję.")

                    all_filtered_distances = [r[0] for r in filtered_results] # Wyciągamy tylko odległości
                    if all_filtered_distances:
                        average_apparent = sum(all_filtered_distances) / len(all_filtered_distances)
                        dip_rad = math.radians(dip_angle)
                        average_real = average_apparent * math.sin(dip_rad)

                        messages.AddMessage("--- Statystyki Globalne (dla odcinków prostopadłych) ---")
                        messages.AddMessage(f"Średnia miąższość pozorna: {average_apparent:.2f} m")
                        messages.AddMessage(f"Średnia miąższość rzeczywista: {average_real:.2f} m")
                        messages.AddMessage("---------------------------------------------------------")
                    
                    # Znajdź wynik o maksymalnej długości (bez zmian)
                    best_result = max(filtered_results, key = lambda item: item[0])
                    
                    apparent_thickness = best_result[0]
                    start_point_coords = best_result[1]
                    end_point_coords = best_result[2]
                    messages.AddMessage(f"Znaleziono najdłuższą odległość (optymistyczną) z filtrowaniem: {apparent_thickness:.2f} m")
                
                # Wspólne czyszczenie dla obu metod globalnych
                arcpy.management.Delete(temp_points)

            # CZĘŚĆ 2: Obliczenia i tworzenie wyniku (wspólne dla wszystkich metod)
            if apparent_thickness is None:
                raise Exception("Nie udało się wyznaczyć miąższości pozornej. Sprawdź parametry.")

            messages.AddMessage("Obliczanie miąższości rzeczywistej...")
            dip_rad = math.radians(dip_angle)
            true_thickness = apparent_thickness * math.sin(dip_rad)
            messages.AddMessage(f"OBLICZONO MIĄŻSZOŚĆ RZECZYWISTĄ: {true_thickness:.2f} m")

            messages.AddMessage("Tworzenie warstwy wynikowej...")
            arcpy.management.CreateFeatureclass(os.path.dirname(out_line), os.path.basename(out_line), "POLYLINE", spatial_reference=spatial_ref)
            arcpy.management.AddField(out_line, "Miazszosc_Pozorna", "DOUBLE")
            arcpy.management.AddField(out_line, "Miazszosc_Rzeczywista", "DOUBLE")

            with arcpy.da.InsertCursor(out_line, ["SHAPE@", "Miazszosc_Pozorna", "Miazszosc_Rzeczywista"]) as cursor:
                start_p = arcpy.Point(*start_point_coords)
                end_p = arcpy.Point(*end_point_coords)
                line_geometry = arcpy.Polyline(arcpy.Array([start_p, end_p]), spatial_ref)
                cursor.insertRow([line_geometry, apparent_thickness, true_thickness])

            messages.AddMessage(f"Zapisano wynik w: {out_line}. Wyznaczone pomiary znajdują się w tabeli atrybutów.")
            messages.AddMessage("Zakończono pomyślnie!")

        except Exception as e:
            messages.AddError(f"Wystąpił błąd: {e}")
            raise # Rzuć błąd, aby narzędzie zakończyło się jako "nieudane"

        return

class ObliczBladKierunku:
    def __init__(self):
        self.label = "Oblicz Błąd Kierunku (Dir)"
        self.description = "Oblicza błąd kierunku (Dir) poprzez analizę odchyleń między dwiema liniami uskoków."

    def getParameterInfo(self):
        # Parametr 0: Uskok wyznaczony przez użytkownika
        param0 = arcpy.Parameter(
            displayName = "Wyznaczony lineament",
            name = "in_fault_user",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )
        param0.filter.list = ["Polyline"]

        # Parametr 1: Uskok referencyjny (z literatury)
        param1 = arcpy.Parameter(
            displayName = "Lineament referencyjny",
            name = "in_fault_reference",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )
        param1.filter.list = ["Polyline"]

        # Parametr 2: Interwał generowania tranzytów
        param2 = arcpy.Parameter(
            displayName = "Interwał pomiaru",
            name = "transect_interval",
            datatype = "GPDouble",
            parameterType = "Required",
            direction = "Input"
        )
        param2.value = 20.0

        # Parametr 3: Długość tranzytów (opcjonalna)
        param3 = arcpy.Parameter(
            displayName = "Długość linii pomiarowych",
            name = "transect_length",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )

        # Parametr 4: Wynikowa warstwa liniowa
        param4 = arcpy.Parameter(
            displayName = "Wynikowe linie pomiaru",
            name = "out_measurement_lines",
            datatype = "DEFeatureClass",
            parameterType = "Required",
            direction = "Output"
        )

        # Parametr 5: Wynikowa tabela ze statystykami
        param5 = arcpy.Parameter(
            displayName = "Wynikowa tabela ze statystykami",
            name = "out_statistics_table",
            datatype = "DETable",
            parameterType = "Required",
            direction = "Output"
        )

        return [param0, param1, param2, param3, param4, param5]

    def updateParameters(self, parameters):
        """
        (Opcjonalne) Tutaj można dodać logikę dynamicznego interfejsu.
        Na razie pozostaje puste.
        """
        return

    def updateMessages(self, parameters):
        """
        (Opcjonalne) Tutaj można dodać walidację parametrów na żywo.
        Na razie pozostaje puste.
        """
        return

    def execute(self, parameters, messages):
        # --- ETAP 0: Pobranie parametrów i przygotowanie środowiska ---
        in_fault_user = parameters[0].valueAsText
        in_fault_reference = parameters[1].valueAsText
        transect_interval = parameters[2].value
        transect_length_manual = parameters[3].value # Może być None
        out_measurement_lines = parameters[4].valueAsText
        out_statistics_table = parameters[5].valueAsText

        arcpy.env.overwriteOutput = True
        
        try:
            messages.AddMessage("Rozpoczynanie analizy błędu kierunku...")

            # --- KROK 1: Przygotowanie i Walidacja Wstępna ---
            messages.AddMessage("Krok 1: Walidacja danych wejściowych...")
            
            # Sprawdzenie zgodności układów współrzędnych
            desc_user = arcpy.Describe(in_fault_user)
            desc_ref = arcpy.Describe(in_fault_reference)
            if desc_user.spatialReference.name != desc_ref.spatialReference.name:
                raise Exception("Układy współrzędnych obu warstw uskoków muszą być identyczne!")
            spatial_ref = desc_user.spatialReference

            # Pobranie geometrii uskoków (zakładamy, że są to pojedyncze linie)
            with arcpy.da.SearchCursor(in_fault_user, ["SHAPE@"]) as cursor:
                fault_user_geom = next(cursor)[0]
            with arcpy.da.SearchCursor(in_fault_reference, ["SHAPE@"]) as cursor:
                fault_ref_geom = next(cursor)[0]

            # --- KROK 2: Przygotowanie Linii Bazowej dla Tranzytów ---
            messages.AddMessage("Krok 2: Przygotowanie linii bazowej do generowania pomiarów...")

            # Obliczenie wspólnej otoczki obu uskoków
            env_user = fault_user_geom.extent
            env_ref = fault_ref_geom.extent
            common_extent = arcpy.Extent(
                min(env_user.XMin, env_ref.XMin), min(env_user.YMin, env_ref.YMin),
                max(env_user.XMax, env_ref.XMax), max(env_user.YMax, env_ref.YMax)
            )

            # Określenie długości tranzytów (automatycznie lub manualnie)
            if transect_length_manual is None:
                transect_length = max(common_extent.width, common_extent.height) * 1.2
                messages.AddMessage(f"Automatycznie obliczona długość linii pomiarowych: {int(transect_length)} m")
            else:
                transect_length = transect_length_manual
                messages.AddMessage(f"Użyto ręcznie zdefiniowanej długości linii pomiarowych: {int(transect_length)} m")

                        # Obliczenie azymutu biegu (line bearing) na tymczasowej kopii
            temp_fault_user = "in_memory/temp_fault_user_for_bearing"
            arcpy.management.CopyFeatures(in_fault_user, temp_fault_user)
            
            # 1. NAJPIERW dodaj puste pole
            arcpy.management.AddField(temp_fault_user, "line_bearing", "DOUBLE")
            
            # 2. DOPIERO TERAZ wypełnij je wartościami
            arcpy.management.CalculateGeometryAttributes(
                in_features=temp_fault_user,
                geometry_property=[["line_bearing", "LINE_BEARING"]],
                coordinate_system=spatial_ref
            )
            with arcpy.da.SearchCursor(temp_fault_user, ["line_bearing"]) as cursor:
                row = next(cursor, None)
                if row is None or row[0] is None:
                    raise Exception("Nie udało się obliczyć azymutu (line bearing) dla uskoku użytkownika.")
                line_bearing_deg = row[0]

            # # Obliczenie azymutu biegu (line bearing) uskoku użytkownika
            # temp_bearing_table = "in_memory/bearing_table"
            # arcpy.management.CalculateGeometryAttributes(in_fault_user, [["line_bearing", "LINE_BEARING"]], "", "", spatial_ref)
            # with arcpy.da.SearchCursor(in_fault_user, ["line_bearing"]) as cursor:
            #     line_bearing_deg = next(cursor)[0]
            
            # Stworzenie "wirtualnej" linii bazowej w pamięci Pythona
            center_x, center_y = common_extent.XMin + common_extent.width / 2, common_extent.YMin + common_extent.height / 2
            bearing_rad = math.radians(line_bearing_deg)
            baseline_len = math.sqrt(common_extent.width**2 + common_extent.height**2) * 1.2
            messages.AddMessage(f"Automatycznie obliczona długość linii bazowej: {int(baseline_len)} m")
            start_x = center_x - (baseline_len / 2) * math.sin(bearing_rad)
            start_y = center_y - (baseline_len / 2) * math.cos(bearing_rad)
            end_x = center_x + (baseline_len / 2) * math.sin(bearing_rad)
            end_y = center_y + (baseline_len / 2) * math.cos(bearing_rad)
            
            baseline_geom = arcpy.Polyline(arcpy.Array([arcpy.Point(start_x, start_y), arcpy.Point(end_x, end_y)]), spatial_ref)
            
            # --- KROK 3: Generowanie Surowych Tranzytów ---
            messages.AddMessage("Krok 3: Generowanie prostopadłych linii pomiarowych (tranzytów)...")
            raw_transects = "in_memory/raw_transects"
            arcpy.management.GenerateTransectsAlongLines(
                baseline_geom,
                raw_transects,
                f"{transect_interval} Meters",
                f"{transect_length} Meters"
            )

            # --- KROK 4: Przecięcie, Filtracja i Tworzenie Linii Pomiarowych ---
            messages.AddMessage("Krok 4: Filtrowanie i tworzenie finalnych linii pomiaru...")
            valid_transect_geometries = []
            
            with arcpy.da.SearchCursor(raw_transects, ["SHAPE@"]) as cursor:
                for row in cursor:
                    transect_geom = row[0]
                    # Znajdź punkty przecięcia z obiema liniami uskoków
                    intersections_user = transect_geom.intersect(fault_user_geom, 1) # 1 = punkty
                    intersections_ref = transect_geom.intersect(fault_ref_geom, 1)

                    # Warunek filtra: muszą istnieć przecięcia z OBIEMA liniami
                    if intersections_user.pointCount > 0 and intersections_ref.pointCount > 0:
                        # Znajdź najbliższą parę punktów (jeden z uskoku usera, drugi z referencyjnego)
                        min_dist = float('inf')
                        best_pair = (None, None)
                        for p_user in intersections_user:
                            for p_ref in intersections_ref:
                                dist = math.sqrt((p_user.X - p_ref.X)**2 + (p_user.Y - p_ref.Y)**2)
                                if dist < min_dist:
                                    min_dist = dist
                                    best_pair = (p_user, p_ref)
                        
                        # Stwórz nową, krótką linię pomiędzy najlepszą parą punktów
                        if best_pair[0]:
                            final_line = arcpy.Polyline(arcpy.Array([best_pair[0], best_pair[1]]), spatial_ref)
                            valid_transect_geometries.append(final_line)
            
            arcpy.management.Delete(raw_transects)
            if not valid_transect_geometries:
                raise Exception("Nie udało się wygenerować żadnych linii pomiarowych. Sprawdź, czy uskoki się przecinają lub czy interwał nie jest zbyt duży.")

            # --- KROK 5: Zapisanie Wyników Geometrycznych ---
            messages.AddMessage(f"Krok 5: Zapisywanie {len(valid_transect_geometries)} linii pomiarowych...")
            arcpy.management.CreateFeatureclass(os.path.dirname(out_measurement_lines), os.path.basename(out_measurement_lines), "POLYLINE", spatial_reference=spatial_ref)
            with arcpy.da.InsertCursor(out_measurement_lines, ["SHAPE@"]) as cursor:
                for geom in valid_transect_geometries:
                    cursor.insertRow([geom])

            # --- KROK 6: Obliczenia Statystyczne ---
            messages.AddMessage("Krok 6: Obliczanie statystyk błędu...")
            lengths = [row[0] for row in arcpy.da.SearchCursor(out_measurement_lines, ["SHAPE@LENGTH"])]
            L = fault_user_geom.length

            min_val, max_val = min(lengths), max(lengths)
            mean_val = sum(lengths) / len(lengths)
            std_val = np.std(lengths) # Używamy NumPy do odchylenia standardowego

            # Wzór na błąd E
            error_E = ((max_val - min_val) * std_val * 90) / (mean_val * L)
            messages.AddMessage(f"Obliczono błąd odchyłki (E): {error_E:.4f} stopni")

            # --- KROK 7: Zapisanie Wyników Statystycznych ---
            messages.AddMessage("Krok 7: Zapisywanie statystyk do tabeli...")
            arcpy.management.CreateTable(os.path.dirname(out_statistics_table), os.path.basename(out_statistics_table))
            fields_to_add = [
                ["Blad_E_stopnie", "DOUBLE"], ["Min_odchylka_m", "DOUBLE"], ["Max_odchylka_m", "DOUBLE"],
                ["Srednia_odchylka_m", "DOUBLE"], ["Odch_stand_m", "DOUBLE"], ["Dlugosc_uskoku_L_m", "DOUBLE"]
            ]
            for field_name, field_type in fields_to_add:
                arcpy.management.AddField(out_statistics_table, field_name, field_type)

            with arcpy.da.InsertCursor(out_statistics_table, [f[0] for f in fields_to_add]) as cursor:
                cursor.insertRow([error_E, min_val, max_val, mean_val, std_val, L])

            messages.AddMessage("\nZakończono pomyślnie!")

        except Exception as e:
            import traceback
            error_msg = str(e)
            messages.AddError(f"Wystąpił błąd: {error_msg}")
            tb_lines = traceback.format_exc().split('\n')
            for line in tb_lines:
                if line.strip(): messages.AddMessage(f"  {line}")
            raise

        return