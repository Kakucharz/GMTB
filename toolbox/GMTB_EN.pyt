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

        self.tools = [GenerateIntersection, CalculateThickness]

class GenerateIntersection:
    def __init__(self):
        self.label = "Generate Intersection Lines"
        self.description = "Creates geological plane and finds its intersection with DTM"

    def getParameterInfo(self): #tool parameters
        #Param 0: method
        param0 = arcpy.Parameter(
            displayName = "Method for generating a plane",
            name = "method",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input"
        )
        param0.filter.type = "ValueList"
        param0.filter.list = [
            "One point with dip/dir",
            "Three point method"
        ]

        param0.value = param0.filter.list[1] #domyślna wartość parametru

        #Param 1: input points
        param1 = arcpy.Parameter(
            displayName = "Input point layer",
            name = "input_points",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )

        param1.filter.list = ["Point"] #akceptuje tylko warstwy punktowe

        #Param 2: orientation input method
        param2 = arcpy.Parameter(
            displayName = "Set the orientation",
            name = "one_point_method",
            datatype = "GPString",
            parameterType = "Optional", #widoczny tylko w metodzie 1P
            direction = "Input"
        )
        param2.filter.type = "ValueList"
        param2.filter.list = ["Manual entry", "Read from the attribute table"]
        param2.value = param2.filter.list[0]

        #Parametr 1: Kierunek zapadania Dir
        param3 = arcpy.Parameter(
            displayName = "Dip direction (Dir)",
            name = "dir_value_manual",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )

        #Parametr 1: kąt upadu Dip
        param4 = arcpy.Parameter(
            displayName = "Dip angle (Dip)",
            name = "dip_value_manual",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )

        #Param 5: Dir input field
        param5 = arcpy.Parameter(
            displayName = "Dip direction (Dir)",
            name = "dir_field",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input"
        )
        param5.filter.type = "Field"
        param5.parameterDependencies = [param1.name]

        #Param 6: Dip input field
        param6 = arcpy.Parameter(
            displayName = "Dip angle (Dip)",
            name = "dip_field",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input"
        )
        param6.filter.type = "Field"
        param6.parameterDependencies = [param1.name]

        #Promień linii intersekcyjnej
        param7 = arcpy.Parameter(
            displayName = "Size of the analysis area [m]",
            name = "analysis_size",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )
        param7.value = 1000 #domyślna wartość

        # Parametr 5: Maksymalna odległość PIONOWA
        param8 = arcpy.Parameter(
            displayName = "Max. vertical distance from the ground [m]",
            name = "vertical_distance",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )
        param8.value = 500 #domyślna wartość

        #Parametr 1: raster NMT
        param9 = arcpy.Parameter(
            displayName = "Digital Terrain Model (DTM)",
            name = "input_nmt_raster",
            datatype = "GPRasterLayer",
            parameterType = "Required",
            direction = "Input"
        )

        #Parametr 2: ścieżka do zapisu wynikowego rastra płaszczyzny
        param10 = arcpy.Parameter(
            displayName = "Output TIN of geological plane",
            name = "out_surface_tin",
            datatype = "DETin", 
            parameterType = "Required",
            direction = "Output"
        )

        #Parametr 3: ścieżka do zapisu wynikowej linii intersekcyjnej
        param11 = arcpy.Parameter(
            displayName = "Output intersection line",
            name = "out_intersection_line",
            datatype = "DEFeatureClass",
            parameterType = "Required",
            direction = "Output"
        )

        #Param 12: add to scene checkbox
        param12 = arcpy.Parameter(
            displayName = "Add output to the Scene",
            name = "add_to_scene",
            datatype = "GPBoolean",
            parameterType = "Optional",
            direction = "Input"
        )
        param12.value = False

        #Param13: dropdown list with scenes
        param13 = arcpy.Parameter(
            displayName = "Choose the Scene",
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
        """Modifies parameters."""

        is_one_point_method = (parameters[0].valueAsText == "One point with dip/dir")

        # Włączamy lub wyłączamy całą sekcję parametrów dla tej metody
        parameters[2].enabled = is_one_point_method  # Przełącznik Wpisz/Tabela
        
        # Jeśli sekcja jest włączona, uruchamiamy wewnętrzną logikę
        if is_one_point_method:
            sub_method = parameters[2].valueAsText
            
            # Jeśli wybrano "Wpisz ręcznie"
            if sub_method == "Manual entry":
                parameters[3].enabled = True  # Pokaż manualny Dir
                parameters[4].enabled = True  # Pokaż manualny Dip
                parameters[5].enabled = False # UKRYJ pole Dir
                parameters[6].enabled = False # UKRYJ pole Dip
            
            # Jeśli wybrano "Read from the attribute table"
            elif sub_method == "Read from the attribute table":
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
        """Validates values and raises errors"""

        # Walidacja pola Dir (parametr 2)
        if parameters[3].enabled and parameters[3].value is not None:
            if not (0 <= parameters[3].value < 360):
                parameters[3].setErrorMessage("The dip direction (Dir) must be between values of 0-359.")
                
        # Walidacja pola Dip (parametr 3)
        if parameters[4].enabled and parameters[4].value is not None:
            if not (0 <= parameters[4].value <= 90):
                parameters[4].setErrorMessage("The dip angle (Dip) must be between values of 0-90.")

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
            
            if method == "One point with dip/dir":
                messages.AddMessage("One point method: Calculating plane parameters...")
                if sub_method == "Manual entry":
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
                    if row is None or row[2] is None or row[2] < -1e38: raise Exception("Input point is outside the DTM extent.")
                    x0, y0, z0 = row[0], row[1], row[2]
                arcpy.management.Delete(temp_point_z)
                
                #zamiana Dip/Dir na wektor normalny (nx, ny, nz) za pomocą trygonometrii
                dip_rad, dir_rad = math.radians(dip_degrees), math.radians(dir_degrees)
                nx, ny, nz = math.sin(dip_rad) * math.sin(dir_rad), math.sin(dip_rad) * math.cos(dir_rad), math.cos(dip_rad)
                extent = arcpy.Describe(input_points).extent
                center_x, center_y = (extent.XMin + extent.XMax) / 2, (extent.YMin + extent.YMax) / 2

            elif method == "Three point method":
                messages.AddMessage("Three point method: Calculating plane values...")
                if int(arcpy.management.GetCount(input_points)[0]) != 3: raise Exception("The minimum of 3 points are needed for this method.")
                
                points_3d_temp = "in_memory/points_with_z"; arcpy.sa.ExtractValuesToPoints(input_points, input_nmt, points_3d_temp)
                coords = [row for row in arcpy.da.SearchCursor(points_3d_temp, ["SHAPE@X", "SHAPE@Y", "RASTERVALU"])]; arcpy.management.Delete(points_3d_temp)
                (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = coords[0], coords[1], coords[2]
                
                #zamiana 3 punkty na wektor normalny (nx, ny, nz) za pomocą iloczynu wektorowego
                nx, ny, nz = (y1-y2)*(z3-z2)-(y3-y2)*(z1-z2), -((x1-x2)*(z3-z2)-(x3-x2)*(z1-z2)), (x1-x2)*(y3-y2)-(x3-x2)*(y1-y2)
                x0, y0, z0 = x2, y2, z2
                center_x, center_y = (x1+x2+x3)/3, (y1+y2+y3)/3

            if nz == 0: raise Exception("The plane is vertical. This case is not currently supported by GMTB.")

            #CZĘŚĆ 2: WSPÓLNY POTOK PRZETWARZANIA
            messages.AddMessage("The processing begins...")
            
            #ETAP W1: Definicja obszaru i środowiska
            spatial_ref = arcpy.Describe(input_nmt).spatialReference
            half_size = analysis_size / 2
            min_x, max_x, min_y, max_y = center_x-half_size, center_x+half_size, center_y-half_size, center_y+half_size
            square_polygon = arcpy.Polygon(arcpy.Array([arcpy.Point(min_x, min_y), arcpy.Point(min_x, max_y), arcpy.Point(max_x, max_y), arcpy.Point(max_x, min_y)]), spatial_ref)
            temp_mask_path = "in_memory/analysis_mask"
            arcpy.management.CopyFeatures(square_polygon, temp_mask_path)
            arcpy.env.extent, arcpy.env.mask, arcpy.env.cellSize, arcpy.env.outputCoordinateSystem, arcpy.env.snapRaster = square_polygon.extent, temp_mask_path, input_nmt, spatial_ref, input_nmt

            #ETAP W2: Tworzenie siatek NumPy
            messages.AddMessage("NumPy arrays creation...")
            nmt_clipped_raster = arcpy.sa.ExtractByMask(input_nmt, temp_mask_path)
            clipped_nmt_obj = Raster(nmt_clipped_raster)
            lower_left, rows, cols, cell_size = clipped_nmt_obj.extent.lowerLeft, clipped_nmt_obj.height, clipped_nmt_obj.width, clipped_nmt_obj.meanCellWidth
            x_coords = np.linspace(lower_left.X, lower_left.X + cell_size * (cols - 1), cols)
            y_coords = np.linspace(lower_left.Y, lower_left.Y + cell_size * (rows - 1), rows)
            x_grid, y_grid = np.meshgrid(x_coords, y_coords); y_grid = np.flipud(y_grid)
            z_grid_geologic = z0 - (nx/nz) * (x_grid - x0) - (ny/nz) * (y_grid - y0)
            z_grid_nmt = arcpy.RasterToNumPyArray(clipped_nmt_obj, nodata_to_value=np.nan)

            #ETAP W3: Przycinanie pionowe i tworzenie linii intersekcyjnej
            messages.AddMessage("Cutting and finding intersection...")
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
            arcpy.management.Delete(temp_raw_line); messages.AddMessage(f"The intersection line has been saved in: {output_intersection}")

            #ETAP W4: Tworzenie TIN
            messages.AddMessage("TIN layer creation...")

            #przerzedzenie punktów dla wydajności
            density_multiplier = 10
            points_xyz_sparse = np.vstack([
                    x_grid[::density_multiplier, ::density_multiplier].ravel(),
                    y_grid[::density_multiplier, ::density_multiplier].ravel(),
                    z_grid_geologic[::density_multiplier, ::density_multiplier].ravel()
            ]).T

            #usunięcie punktów z NaN
            points_xyz_sparse = points_xyz_sparse[~np.isnan(points_xyz_sparse).any(axis=1)]
            if points_xyz_sparse.shape[0] == 0: raise Exception("Not enough points to create TIN layer.")

            #tworzenie warstwy punktowej 3D
            temp_points_for_tin = "in_memory/sparse_points"
            arcpy.management.CreateFeatureclass("in_memory", "sparse_points", "POINT", spatial_reference=spatial_ref, has_z="ENABLED")

            #dodaj pole Z_VALUE dla TIN
            arcpy.management.AddField(temp_points_for_tin, "Z_VALUE", "DOUBLE")

            with arcpy.da.InsertCursor(temp_points_for_tin, ["SHAPE@XY", "Z_VALUE"]) as cursor:
                for p in points_xyz_sparse: cursor.insertRow(((p[0], p[1]), p[2]))

            arcpy.ddd.CreateTin(output_surface, spatial_ref, f"{temp_points_for_tin} Z_VALUE Mass_Points")
            arcpy.ddd.EditTin(output_surface, [f"{temp_mask_path} <None> Hard_Clip"])
            arcpy.management.Delete(temp_points_for_tin); messages.AddMessage(f"The TIN layer has been saved in: {output_surface}")

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
            
            elif method == "Three point method":
                mag_xy = math.sqrt(nx**2 + ny**2); mag_xyz = math.sqrt(nx**2 + ny**2 + nz**2)
                dip_val = math.degrees(math.asin(mag_xy / mag_xyz)); dir_val = math.degrees(math.atan2(nx, ny))
                if dir_val < 0: dir_val += 360
                arcpy.management.AddField(output_intersection, "Dip", "DOUBLE", field_alias="DIP")
                arcpy.management.AddField(output_intersection, "Dir", "DOUBLE", field_alias="DIR")
                with arcpy.da.UpdateCursor(output_intersection, ["Dip", "Dir"]) as cursor:
                    for row in cursor: cursor.updateRow([dip_val, dir_val])

            messages.AddMessage("\nExecution successful!")

        except Exception as e:
            import traceback
            error_msg = str(e)
            messages.AddError(f"There is an error: {error_msg}")
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

class CalculateThickness:
    def __init__(self):
        self.label = "Calculate Thickness"
        self.description = "Calculates apparent and real thickness based on 2 intersection lines and dip angle."

    def getParameterInfo(self):
        #Param 0: Method
        param0 = arcpy.Parameter(
        displayName="Method",
        name="method",
        datatype="GPString",
        parameterType="Required",
        direction="Input"
        )
        param0.filter.type = "ValueList"
        param0.filter.list = ["Local (in given point", "Global (pessimistic)", "Global (optimistic)"]
        param0.value = param0.filter.list[0]

        #Param 1: linia 1
        param1 = arcpy.Parameter(
            displayName = "1st intersection line",
            name = "in_line_1",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )
        param1.filter.list = ["Polyline"]

        #Param 2: linia 2
        param2 = arcpy.Parameter(
            displayName = "2nd intersection line",
            name = "in_line_2",
            datatype = "GPFeatureLayer",
            parameterType = "Required",
            direction = "Input"
        )
        param2.filter.list = ["Polyline"]

        #Param 3: point
        param3 = arcpy.Parameter(
            displayName = "Point of measurement",
            name = "in_point",
            datatype = "GPFeatureLayer",
            parameterType = "Optional",
            direction = "Input"
        )
        param3.filter.list = ["Point"]

        #Param 4: Dip input method
        param4 = arcpy.Parameter(
            displayName = "Set the orientation",
            name = "dip_input_method",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input"
        )
        param4.filter.type = "ValueList"
        param4.filter.list = ["Manual entry", "Read from the line 1"]
        param4.value = param4.filter.list[0]

        #Param 5: Kąt zapadania (DIP)
        param5 = arcpy.Parameter(
            displayName = "Dip angle (dip)",
            name = "dip_angle",
            datatype = "GPDouble",
            parameterType = "Optional",
            direction = "Input"
        )

        #Param 6: wybór pola dla kąta
        param6 = arcpy.Parameter(
            displayName = "Dip field (dip)",
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
            displayName = "Output thickness line",
            name = "out_measurement_line",
            datatype = "DEFeatureClass",
            parameterType = "Required",
            direction = "Output"
        )

        #Parametr 1: raster NMT
        param8 = arcpy.Parameter(
            displayName = "Digital Terrain Model (DTM)",
            name = "input_nmt_raster",
            datatype = "GPRasterLayer",
            parameterType = "Required",
            direction = "Input"
        )

        return [param0, param1, param2, param3, param4, param5, param6, param7, param8]

    def updateParameters(self, parameters):
        # Pokaż/ukryj parametr punktu w zależności od wybranej metody
        if parameters[0].value == "Local (in given point)":
            parameters[3].enabled = True
            parameters[3].parameterType = "Required" # Staje się wymagany
        else:
            parameters[3].enabled = False
            parameters[3].parameterType = "Optional" # Musi być opcjonalny, gdy ukryty

        # Widocznoać pola kąt
        dip_method = parameters[4].value
        if dip_method == "Manual entry":
            parameters[5].enabled = True
            parameters[5].parameterType = "Required"
        else: 
            parameters[5].enabled = False
            parameters[5].parameterType = "Optional"

        dip_method = parameters[4].value
        manual_dip_param = parameters[5]
        field_dip_param = parameters[6] 

        if dip_method == "Manual entry":
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
                parameters[5].setErrorMessage("The dip angle (Dip) must be within (0, 90].")
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
        input_nmt = parameters[8].valueAsText

        arcpy.env.overwriteOutput = True

        try:
            #wybór metody odczytu kąta
            dip_angle = None
            if dip_input_method == "Manual entry":
                dip_angle = dip_angle_manual
                if dip_angle is None:
                    raise ValueError("Could not read the dip angle (dip).")
                messages.AddMessage(f"The manual entry for dip angle: {dip_angle}°")
            
            else:
                messages.AddMessage(f"Extracting dip angle from field: '{dip_field_name}'...")
                
                # Sprawdź, czy użytkownik wybrał pole
                if not dip_field_name:
                    raise ValueError("No Dip field has been selected.")
                
                # Odczytaj wartość z wybranego pola
                with arcpy.da.SearchCursor(in_line_1, [dip_field_name]) as cursor:
                    row = next(cursor, None)
                    if row is None: raise Exception("Layer '1st line' is empty. Could not extract value.")
                    if row[0] is None: raise Exception(f"The dip field '{dip_field_name}' is Null.")
                    
                    dip_angle = float(row[0])
                    messages.AddMessage(f"The dip angle: {dip_angle}°")

            # Walidacja odczytanego/wpisanego kąta
            if not (0 < dip_angle <= 90):
                raise ValueError(f"Dip angle ({dip_angle}°) is outside of the expected extent (0, 90].")

            # Inicjalizacja zmiennych, które zostaną wypełnione w zależności od metody
            apparent_thickness = None
            start_point_coords = None
            end_point_coords = None
            spatial_ref = arcpy.Describe(in_line_1).spatialReference

            #CZĘŚĆ 1: Wyznaczenie miąższości pozornej zgodnie z wybraną metodą
            if method == "Local (in given point)":
                messages.AddMessage("Calculating local method...")
                
                # Znalezienie punktu na Linii 1
                arcpy.analysis.Near(in_point, in_line_1, location=True)
                with arcpy.da.SearchCursor(in_point, ["NEAR_X", "NEAR_Y"]) as cursor:
                    row = next(cursor, None)
                    if row and row[0] != -1:
                        start_point_coords = (row[0], row[1])
                if not start_point_coords:
                    raise Exception("The point of measurement could not be found on the 1st line.")

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
                    raise Exception("The point of measurement could not be found on the 2nd line.")
                
                messages.AddMessage(f"APPARENT THICKNESS: {apparent_thickness:.2f} m")

            elif method in ["Global (pessimistic)", "Global (optimistic)"]:
                messages.AddMessage(f"Calculating global method: {method}...")
                
                # Dyskretyzacja
                temp_points = "in_memory/densified_points"
                arcpy.management.GeneratePointsAlongLines(in_line_1, temp_points, "DISTANCE", Distance="1 Meters")
                
                # Analiza Near
                arcpy.analysis.Near(temp_points, in_line_2, location=True, angle=True)
                
                # Zebranie wyników i wybór
                if method == "Global (pessimistic)":
                    # Logika dla pesymistycznej: szukamy absolutnego minimum
                    results = {}
                    with arcpy.da.SearchCursor(temp_points, ["SHAPE@X", "SHAPE@Y", "NEAR_DIST", "NEAR_X", "NEAR_Y"]) as cursor:
                        for row in cursor:
                            dist = row[2]
                            if dist != -1:
                                results[dist] = ((row[0], row[1]), (row[3], row[4]))
                    if not results:
                        raise Exception("The distance between lines could not be found.")

                    all_distances = list(results.keys())
                    if all_distances:
                        average_apparent = sum(all_distances) / len(all_distances)
                        dip_rad = math.radians(dip_angle)
                        average_real = average_apparent * math.sin(dip_rad)
                        
                        messages.AddMessage("GLOBAL STATISTICS:")
                        messages.AddMessage(f"Average apparent thickness: {average_apparent:.2f} m")
                        messages.AddMessage(f"Average real thickness: {average_real:.2f} m")
                        messages.AddMessage("--------------------------")
                    
                    target_distance = min(results.keys())
                    messages.AddMessage(f"The shortest (pessimistic) distance: {target_distance:.2f} m")
                    start_point_coords, end_point_coords = results[target_distance]
                    apparent_thickness = target_distance

                else: #logika dla optymistycznej
                    messages.AddMessage("Filtering the outputs for the longest perpendicular value...")
                    
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
                    
                    messages.AddMessage(f"The general angle of planes: {general_angle_deg:.1f}°. Expected angles: {perpendicular_angle_1:.1f}° or {perpendicular_angle_2:.1f}°")
                    
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
                        raise Exception(f"No value could be found for given angle tolerance {angle_tolerance}°. Try other data or change tolerance.")

                    all_filtered_distances = [r[0] for r in filtered_results] # Wyciągamy tylko odległości
                    if all_filtered_distances:
                        average_apparent = sum(all_filtered_distances) / len(all_filtered_distances)
                        dip_rad = math.radians(dip_angle)
                        average_real = average_apparent * math.sin(dip_rad)

                        messages.AddMessage("GLOBAL STATISTICS FOR PERPENDICULAR VALUES")
                        messages.AddMessage(f"Average apparent thickness: {average_apparent:.2f} m")
                        messages.AddMessage(f"Average real thickness: {average_real:.2f} m")
                        messages.AddMessage("---------------------------------------------------------")
                    
                    # Znajdź wynik o maksymalnej długości (bez zmian)
                    best_result = max(filtered_results, key = lambda item: item[0])
                    
                    apparent_thickness = best_result[0]
                    start_point_coords = best_result[1]
                    end_point_coords = best_result[2]
                    messages.AddMessage(f"The longest (optimistic) distance with filtering: {apparent_thickness:.2f} m")
                
                # Wspólne czyszczenie dla obu metod globalnych
                arcpy.management.Delete(temp_points)

            # CZĘŚĆ 2: Obliczenia i tworzenie wyniku (wspólne dla wszystkich metod)
            if apparent_thickness is None:
                raise Exception("Could not resolve apparent thickness.")

            ### POCZĄTEK NOWEJ LOGIKI 3D ###
            messages.AddMessage("Real thickness calculation with 3D vector method...")

            # współrzędne Z dla obu punktów z NMT
            (x1, y1), (x2, y2) = start_point_coords, end_point_coords

            temp_2_points = "in_memory/temp_2_points_for_z"
            arcpy.management.CreateFeatureclass("in_memory", "temp_2_points_for_z", "POINT", spatial_reference=spatial_ref)
            with arcpy.da.InsertCursor(temp_2_points, ["SHAPE@XY"]) as cursor:
                cursor.insertRow([(x1, y1)])
                cursor.insertRow([(x2, y2)])
            
            points_with_z = "in_memory/points_with_z_result"
            arcpy.sa.ExtractValuesToPoints(temp_2_points, input_nmt, points_with_z, "NONE", "VALUE_ONLY")
            
            # Odczytaj wartości Z
            z_values = [row[0] for row in arcpy.da.SearchCursor(points_with_z, ["RASTERVALU"])]
            arcpy.management.Delete(temp_2_points); arcpy.management.Delete(points_with_z)

            if len(z_values) < 2 or z_values[0] is None or z_values[1] is None:
                 raise Exception("Could not read the Z from DTM for one of the measurement points. The point is propably beyond the DTM extent.")
            
            z1, z2 = z_values[0], z_values[1]
            
            # Odczyt kierunku upadu (Dir) z atrybutów Linii 1
            dir_angle = None
            if 'dir' in [f.name.lower() for f in arcpy.ListFields(in_line_1)]:
                with arcpy.da.SearchCursor(in_line_1, ["Dir"]) as cursor:
                    row = next(cursor, None)
                    if row and row[0] is not None: dir_angle = float(row[0])
            if dir_angle is None:
                raise Exception("Could not read the dip direction (Dir) value from the attribute table of 'Line 1'.")
            
            # Obliczenia wektorowe
            dip_rad, dir_rad = math.radians(dip_angle), math.radians(dir_angle)
            nx, ny, nz = math.sin(dip_rad) * math.sin(dir_rad), math.sin(dip_rad) * math.cos(dir_rad), math.cos(dip_rad)
            vx, vy, vz = x2 - x1, y2 - y1, z2 - z1
            dot_product = (vx * nx) + (vy * ny) + (vz * nz)
            true_thickness = abs(dot_product)
            
            messages.AddMessage(f"True thickness (calculated in 3D): {true_thickness:.2f} m")

            messages.AddMessage("The output layer creation...")
            arcpy.management.CreateFeatureclass(os.path.dirname(out_line), os.path.basename(out_line), "POLYLINE", spatial_reference=spatial_ref)
            arcpy.management.AddField(out_line, "Apparent_Thickness", "DOUBLE")
            #
            arcpy.management.AddField(out_line, "Real_Thickness_3D", "DOUBLE")

            with arcpy.da.InsertCursor(out_line, ["SHAPE@", "Apparent_Thickness", "Real_Thickness_3D"]) as cursor:
                start_p = arcpy.Point(*start_point_coords)
                end_p = arcpy.Point(*end_point_coords)
                line_geometry = arcpy.Polyline(arcpy.Array([start_p, end_p]), spatial_ref)
                cursor.insertRow([line_geometry, apparent_thickness, true_thickness])

            messages.AddMessage(f"Saved output: {out_line}. The results can be found in the attribute table.")
            messages.AddMessage("Execution successful!")

        except Exception as e:
            messages.AddError(f"There has been an error: {e}")
            raise

        return