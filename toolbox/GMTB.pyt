# -*- coding: utf-8 -*-

import arcpy
import math
import numpy as np
import timeit
import os

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

        self.tools = [GenerujIntersekcje, ObliczMiazszosc]

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
        method = parameters[0].valueAsText
        input_points = parameters[1].valueAsText
        sub_method = parameters[2].valueAsText
        dir_degrees = parameters[3].value
        dip_degrees = parameters[4].value
        dir_field = parameters[5].valueAsText
        dip_field = parameters[6].valueAsText
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

        if method == "Jeden punkt z orientacją":
            messages.AddMessage("Uruchomiono logikę dla metody: 1 punkt + Dip/Dir")
            
            dir_degrees = None
            dip_degrees = None
            
            if sub_method == "Manual input":
                messages.AddMessage("Pobieranie orientacji z wartości wpisanych ręcznie...")
                dir_degrees = parameters[3].value
                dip_degrees = parameters[4].value

                if dir_degrees is None or dip_degrees is None:
                    raise ValueError("The value for dip or dir parameter is missing")
            
            elif sub_method == "Choose column":
                messages.AddMessage("Pobieranie orientacji z tabeli atrybutów...")
                if not dir_field or not dip_field:
                    raise ValueError("Proszę wybrać pola z tabeli atrybutów dla wartości Dir i Dip.")
                
                with arcpy.da.SearchCursor(input_points, [dir_field, dip_field]) as cursor:
                    row = next(cursor, None)
                    if row is None: raise Exception("Warstwa wejściowa nie zawiera punktów.")
                    
                    try:
                        # convert to float, if possible
                        dir_degrees = float(row[0])
                        dip_degrees = float(row[1])
                    except (TypeError, ValueError):
                        raise TypeError(f"Nieprawidłowy format danych w tabeli atrybutów. "
                                        f"Pola '{dir_field}' i '{dip_field}' muszą zawierać wartości liczbowe, a nie tekst lub puste komórki.")

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

                #ETAP 8: DODANIE WYNIKU DO SCENY
                try:
                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                    map_2d_to_add_to = None

                    if aprx.activeMap and aprx.activeMap.mapType == "MAP":
                        map_2d_to_add_to = aprx.activeMap
                        messages.AddMessage(f"Aktywny widok to mapa 2D ('{map_2d_to_add_to.name}').")
                    else:
                        map_list_2d = [m for m in aprx.listMaps() if m.mapType == "MAP"]
                        if map_list_2d:
                            map_2d_to_add_to = map_list_2d[0] 
                            messages.AddMessage(f"Aktywny widok nie jest mapą 2D. Znaleziono inną mapę do dodania wyniku: '{map_2d_to_add_to.name}'.")

                    if map_2d_to_add_to:
                        messages.AddMessage("Dodawanie linii intersekcyjnej do mapy 2D...")
                        map_2d_to_add_to.addDataFromPath(output_intersection)
                    else:
                        # Opcja ostateczna: Nie ma ŻADNYCH map 2D w całym projekcie
                        messages.AddWarning("Nie znaleziono żadnej mapy 2D w projekcie. Linia intersekcyjna nie została dodana do widoku 2D.")

                    if add_to_scene and target_scene_name:
                        messages.AddMessage(f"\nDodawanie wyników do wybranej sceny 3D: '{target_scene_name}'...")
                        scene = next((m for m in aprx.listMaps() if m.mapType == "SCENE" and m.name == target_scene_name), None)
                        
                        if not scene:
                            messages.AddWarning(f"Nie znaleziono sceny o nazwie: '{target_scene_name}'. Pomięto dodawanie warstw do sceny.")
                        else:
                            messages.AddMessage("Dodawanie warstwy TIN do sceny...")
                            scene.addDataFromPath(output_surface)
                            
                            messages.AddMessage("Dodawanie linii intersekcyjnej do sceny...")
                            scene.addDataFromPath(output_intersection)
                            messages.AddMessage("Pomyślnie dodano warstwy do sceny.")
                
                except Exception as e:
                    messages.AddWarning(f"Wystąpił nieoczekiwany błąd podczas dodawania warstw do widoków: {e}")
                

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
                messages.AddMessage("\n=== PODSUMOWANIE PARAMETRÓW ===")
                messages.AddMessage(f"ZADANE przez użytkownika:")
                messages.AddMessage(f"  - Rozmiar obszaru analizy XY: ±{half_size:.1f} m od punktu")
                messages.AddMessage(f"  - Maks. odległość pionowa: ±{vertical_distance:.1f} m")
                messages.AddMessage(f"  - Oczekiwany zakres Z: {z_min_allowed:.1f} - {z_max_allowed:.1f} m n.p.m.")
                messages.AddMessage(f"\nRZECZYWISTE wymiary TIN:")
                messages.AddMessage(f"  - Szerokość X: {tin_extent.XMax - tin_extent.XMin:.1f} m")
                messages.AddMessage(f"  - Wysokość Y: {tin_extent.YMax - tin_extent.YMin:.1f} m")
                messages.AddMessage(f"  - Rozpiętość Z: {tin_extent.ZMax - tin_extent.ZMin:.1f} m ({tin_extent.ZMin:.1f} - {tin_extent.ZMax:.1f} m n.p.m.)")
                
                #Zapisanie dip i dir do tabeli atrybutów
                arcpy.management.AddField(output_intersection, "Dip", "DOUBLE", field_alias = "DIP")
                arcpy.management.AddField(output_intersection, "Dir", "DOUBLE", field_alias = "DIR")

                with arcpy.da.UpdateCursor(output_intersection, ["Dip", "Dir"]) as cursor:
                    for row in cursor:
                        cursor.updateRow([dip_degrees, dir_degrees])
                
                # Czyszczenie
                arcpy.management.Delete(temp_points_for_tin)
                messages.AddMessage("Zakończono pomyślnie!")
            
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
            messages.AddMessage("Uruchomiono logikę dla metody: 3 punkty")
            
            try:
                # ETAP 1: Walidacja i pobranie 3 punktów wejściowych
                messages.AddMessage("Odczytywanie 3 punktów wejściowych i definiowanie obszaru analizy...")
                
                point_count = int(arcpy.management.GetCount(input_points)[0])
                if point_count != 3:
                    raise Exception(f"Warstwa wejściowa musi zawierać dokładnie 3 punkty. Obecnie zawiera: {point_count}.")

                # Nadanie punktom wysokości (Z) z NMT
                points_3d_temp = "in_memory/points_with_z"
                arcpy.sa.ExtractValuesToPoints(input_points, input_nmt, points_3d_temp, "NONE", "VALUE_ONLY")

                coords_list = []
                with arcpy.da.SearchCursor(points_3d_temp, ["SHAPE@X", "SHAPE@Y", "RASTERVALU"]) as cursor:
                    for row in cursor:
                        if row[2] is None or row[2] < -1e38:
                            raise Exception("Jeden z punktów znajduje się poza zasięgiem NMT lub w obszarze NoData.")
                        coords_list.append(row)
                arcpy.management.Delete(points_3d_temp)
                
                (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = coords_list[0], coords_list[1], coords_list[2]
                
                # Obliczamy centrum na podstawie 3 punktów
                center_x = (x1 + x2 + x3) / 3
                center_y = (y1 + y2 + y3) / 3
                
                # --- OD TEGO MIEJSCA LOGIKA JEST LUSTRZANYM ODBICIEM METODY 1-PUNKTOWEJ ---

                # ETAP 1 i 2: Definicja obszaru i środowiska
                messages.AddMessage(f"Definiowanie kwadratowego obszaru analizy o boku {analysis_size}m...")
                spatial_ref = arcpy.Describe(input_nmt).spatialReference
                half_size = analysis_size / 2
                min_x, max_x = center_x - half_size, center_x + half_size
                min_y, max_y = center_y - half_size, center_y + half_size
                square_polygon = arcpy.Polygon(arcpy.Array([
                    arcpy.Point(min_x, min_y), arcpy.Point(min_x, max_y),
                    arcpy.Point(max_x, max_y), arcpy.Point(max_x, min_y)
                ]), spatial_ref)
                
                temp_mask_path = "in_memory/analysis_mask"
                arcpy.management.CopyFeatures(square_polygon, temp_mask_path)
                arcpy.env.extent, arcpy.env.mask = square_polygon.extent, temp_mask_path
                arcpy.env.cellSize, arcpy.env.outputCoordinateSystem = input_nmt, spatial_ref
                arcpy.env.snapRaster = input_nmt
                
                messages.AddMessage("Jawne przycinanie NMT do obszaru analizy...")
                nmt_clipped_raster = arcpy.sa.ExtractByMask(input_nmt, temp_mask_path)

                # ETAP 3: Obliczenia płaszczyzny
                messages.AddMessage("Obliczanie parametrów płaszczyzny...")
                x0, y0, z0 = x2, y2, z2 # Używamy P2 jako punktu zakotwiczenia
                
                nx = (y1 - y2) * (z3 - z2) - (y3 - y2) * (z1 - z2)
                ny = -((x1 - x2) * (z3 - z2) - (x3 - x2) * (z1 - z2))
                nz = (x1 - x2) * (y3 - y2) - (x3 - x2) * (y1 - y2)
                if nz == 0: raise Exception("Płaszczyzna jest pionowa. Ta metoda nie jest obecnie wspierana.")
                messages.AddMessage(f"Punkt zakotwiczenia: X={x0:.2f}, Y={y0:.2f}, Z={z0:.2f}")

                # ETAP 4: Tworzenie siatek NumPy
                messages.AddMessage("Tworzenie siatek NumPy dla terenu i płaszczyzny...")
                clipped_nmt_obj = Raster(nmt_clipped_raster)
                lower_left, rows, cols, cell_size = clipped_nmt_obj.extent.lowerLeft, clipped_nmt_obj.height, clipped_nmt_obj.width, clipped_nmt_obj.meanCellWidth
                x_coords = np.linspace(lower_left.X, lower_left.X + cell_size * (cols - 1), cols)
                y_coords = np.linspace(lower_left.Y, lower_left.Y + cell_size * (rows - 1), rows)
                x_grid, y_grid = np.meshgrid(x_coords, y_coords)
                y_grid = np.flipud(y_grid)
                z_grid_geologic = z0 - (nx/nz) * (x_grid - x0) - (ny/nz) * (y_grid - y0)
                z_grid_nmt = arcpy.RasterToNumPyArray(clipped_nmt_obj, nodata_to_value=np.nan)

                # ETAP 5: Przycinanie pionowe
                messages.AddMessage(f"Przycinanie płaszczyzny w pionie (max {vertical_distance}m)...")
                diff_grid = z_grid_geologic - z_grid_nmt
                z_grid_geologic[np.abs(diff_grid) > vertical_distance] = np.nan
                z_min_allowed, z_max_allowed = z0 - vertical_distance, z0 + vertical_distance
                z_grid_geologic[(z_grid_geologic < z_min_allowed) | (z_grid_geologic > z_max_allowed)] = np.nan
                
                # ETAP 6: Tworzenie linii intersekcyjnej
                messages.AddMessage("Znajdowanie linii intersekcyjnej...")
                intersection_raster = arcpy.NumPyArrayToRaster(np.where(np.abs(diff_grid) < 1.0, 1, np.nan), lower_left, cell_size, cell_size)
                thinned_raster = arcpy.sa.Thin(arcpy.sa.Int(intersection_raster), "ZERO", "NO_FILTER", "ROUND")
                temp_raw_line = "in_memory/raw_line"
                arcpy.conversion.RasterToPolyline(thinned_raster, temp_raw_line, "ZERO", 0, "NO_SIMPLIFY")
                arcpy.cartography.SmoothLine(temp_raw_line, output_intersection, "PAEK", cell_size * 5)
                arcpy.management.Delete(temp_raw_line)
                messages.AddMessage(f"Zapisano linię intersekcyjną w: {output_intersection}")

                #ETAP 7: TWORZENIE PŁASZCZYZNY TIN
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
                
                temp_points_for_tin = "in_memory/sparse_points"
                arcpy.management.CreateFeatureclass("in_memory", "sparse_points", "POINT", spatial_reference=spatial_ref, has_z="ENABLED")
                arcpy.management.AddField(temp_points_for_tin, "Z_VALUE", "DOUBLE")
                with arcpy.da.InsertCursor(temp_points_for_tin, ["SHAPE@XY", "Z_VALUE"]) as cursor:
                    for p in points_xyz_sparse: cursor.insertRow(((p[0], p[1]), p[2]))
                
                arcpy.ddd.CreateTin(output_surface, spatial_ref, f"{temp_points_for_tin} Z_VALUE Mass_Points")
                arcpy.ddd.EditTin(output_surface, [f"{temp_mask_path} <None> Hard_Clip"])
                arcpy.management.Delete(temp_points_for_tin)
                messages.AddMessage(f"Zapisano przycięty TIN w: {output_surface}")
                
                #ETAP 8: DODANIE WYNIKU DO SCENY
                try:
                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                    map_2d_to_add_to = None

                    if aprx.activeMap and aprx.activeMap.mapType == "MAP":
                        map_2d_to_add_to = aprx.activeMap
                        messages.AddMessage(f"Aktywny widok to mapa 2D ('{map_2d_to_add_to.name}').")
                    else:
                        map_list_2d = [m for m in aprx.listMaps() if m.mapType == "MAP"]
                        if map_list_2d:
                            map_2d_to_add_to = map_list_2d[0] 
                            messages.AddMessage(f"Aktywny widok nie jest mapą 2D. Znaleziono inną mapę do dodania wyniku: '{map_2d_to_add_to.name}'.")

                    if map_2d_to_add_to:
                        messages.AddMessage("Dodawanie linii intersekcyjnej do mapy 2D...")
                        map_2d_to_add_to.addDataFromPath(output_intersection)
                    else:
                        # Opcja ostateczna: Nie ma ŻADNYCH map 2D w całym projekcie
                        messages.AddWarning("Nie znaleziono żadnej mapy 2D w projekcie. Linia intersekcyjna nie została dodana do widoku 2D.")

                    if add_to_scene and target_scene_name:
                        messages.AddMessage(f"\nDodawanie wyników do wybranej sceny 3D: '{target_scene_name}'...")
                        scene = next((m for m in aprx.listMaps() if m.mapType == "SCENE" and m.name == target_scene_name), None)
                        
                        if not scene:
                            messages.AddWarning(f"Nie znaleziono sceny o nazwie: '{target_scene_name}'. Pomięto dodawanie warstw do sceny.")
                        else:
                            messages.AddMessage("Dodawanie warstwy TIN do sceny...")
                            scene.addDataFromPath(output_surface)
                            
                            messages.AddMessage("Dodawanie linii intersekcyjnej do sceny...")
                            scene.addDataFromPath(output_intersection)
                            messages.AddMessage("Pomyślnie dodano warstwy do sceny.")
                
                except Exception as e:
                    messages.AddWarning(f"Wystąpił nieoczekiwany błąd podczas dodawania warstw do widoków: {e}")
                

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
                messages.AddMessage("\n=== PODSUMOWANIE PARAMETRÓW ===")
                messages.AddMessage(f"ZADANE przez użytkownika:")
                messages.AddMessage(f"  - Rozmiar obszaru analizy XY: ±{half_size:.1f} m od punktu")
                messages.AddMessage(f"  - Maks. odległość pionowa: ±{vertical_distance:.1f} m")
                messages.AddMessage(f"  - Oczekiwany zakres Z: {z_min_allowed:.1f} - {z_max_allowed:.1f} m n.p.m.")
                messages.AddMessage(f"\nRZECZYWISTE wymiary TIN:")
                messages.AddMessage(f"  - Szerokość X: {tin_extent.XMax - tin_extent.XMin:.1f} m")
                messages.AddMessage(f"  - Wysokość Y: {tin_extent.YMax - tin_extent.YMin:.1f} m")
                messages.AddMessage(f"  - Rozpiętość Z: {tin_extent.ZMax - tin_extent.ZMin:.1f} m ({tin_extent.ZMin:.1f} - {tin_extent.ZMax:.1f} m n.p.m.)")
                
                #Zapisanie dip i dir do tabeli atrybutów
                messages.AddMessage("Obliczanie wynikowych wartości Dip i Dir z geometrii płaszczyzny...")

                # Obliczanie kąta upadu (Dip) - Równanie 12 z PDF Hasbargena
                # Kąt między wektorem normalnym a pionem
                mag_xy = math.sqrt(nx**2 + ny**2)
                mag_xyz = math.sqrt(nx**2 + ny**2 + nz**2)
                dip_val = math.degrees(math.asin(mag_xy / mag_xyz))

                # Obliczanie kierunku upadu (Dir)
                # Jest to kierunek (azymut) rzutu wektora normalnego na płaszczyznę XY
                dir_val = math.degrees(math.atan2(nx, ny))
                if dir_val < 0:
                    dir_val += 360
                
                messages.AddMessage(f"Obliczono: Dip = {dip_val:.1f}, Dir = {dir_val:.1f}")
                arcpy.management.AddField(output_intersection, "Dip", "DOUBLE", field_alias = "DIP")
                arcpy.management.AddField(output_intersection, "Dir", "DOUBLE", field_alias = "DIR")

                with arcpy.da.UpdateCursor(output_intersection, ["Dip", "Dir"]) as cursor:
                    for row in cursor:
                        cursor.updateRow([dip_val, dir_val])
                
                # Czyszczenie
                arcpy.management.Delete(temp_points_for_tin)
                messages.AddMessage("Zakończono pomyślnie!")

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
#-----------------------------------------------------------------------------------------------------------------------------------------------

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
        param4.filter.list = ["Wprowadź ręcznie", "Odczytaj automatycznie z Linii 1"]
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
        if dip_method == "Wprowadź ręcznie":
            parameters[5].enabled = True
            parameters[5].parameterType = "Required"
        else: 
            parameters[5].enabled = False
            parameters[5].parameterType = "Optional"

        dip_method = parameters[4].value
        manual_dip_param = parameters[5]
        field_dip_param = parameters[6] 

        if dip_method == "Wprowadź ręcznie":
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
        
        # walidacja kąta
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
            if dip_input_method == "Wprowadź ręcznie":
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
                
                # Analiza 
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