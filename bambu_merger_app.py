#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bambu Multi-Plate Studio (Bambu 3MF Plate Merger)
=================================================
Interfaccia grafica moderna per unire più file .3mf con impostazioni di piatto indipendenti.
Sviluppato con CustomTkinter.
"""

import os
import sys
import io
import json
import zipfile
import subprocess
import threading
import xml.etree.ElementTree as ET
from PIL import Image

import customtkinter as ctk
from tkinter import filedialog, messagebox

# Configurazione tema CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

BAMBU_PLATE_SPACING_X = 307.2
BAMBU_PLATE_SPACING_Y = 307.2

OBJECT_OVERRIDE_KEYS = [
    'layer_height',
    'sparse_infill_pattern',
    'sparse_infill_density',
    'wall_loops',
    'top_shell_layers',
    'bottom_shell_layers',
    'top_shell_thickness',
    'bottom_shell_thickness',
    'bottom_color_penetration_layers',
    'top_color_penetration_layers',
    'initial_layer_speed',
    'initial_layer_infill_speed',
    'outer_wall_speed',
    'inner_wall_speed',
    'sparse_infill_speed',
    'internal_solid_infill_speed',
    'top_surface_speed',
    'gap_infill_speed',
    'support_type',
    'enable_support',
    'support_base_pattern',
    'support_interface_pattern',
    'support_interface_spacing',
    'support_interface_top_layers',
    'support_top_z_distance',
    'support_bottom_z_distance',
    'support_threshold_angle',
    'support_on_build_plate_only',
    'support_remove_small_overhang',
    'tree_support_wall_count',
    'brim_type',
    'brim_width',
    'brim_object_gap',
    'raft_first_layer_density',
    'raft_first_layer_expansion',
    'skirt_loops',
    'ironing_flow',
    'ironing_type',
    'ironing_speed',
    'fuzzy_skin',
    'fuzzy_skin_point_distance',
    'fuzzy_skin_thickness',
]

def find_bambu_studio_path():
    """Cerca l'eseguibile di Bambu Studio o OrcaSlicer sul sistema"""
    candidates = [
        r"C:\Program Files\Bambu Studio\bambu-studio.exe",
        r"C:\Program Files (x86)\Bambu Studio\bambu-studio.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BambuStudio\bambu-studio.exe"),
        r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
        r"C:\Program Files (x86)\OrcaSlicer\orca-slicer.exe",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None

def extract_plate_metadata(filepath):
    """Estrae rapidamente metadati e miniatura da un file .3mf"""
    info = {
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'layer_height': 'N/D',
        'is_seq_print': False,
        'infill_pattern': 'N/D',
        'infill_density': 'N/D',
        'wall_loops': 'N/D',
        'bed_type': 'N/D',
        'filaments': [],
        'object_count': 0,
        'thumbnail_img': None,
    }
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            # Thumbnail
            for tname in ['Metadata/plate_1_small.png', 'Metadata/plate_1.png']:
                if tname in z.namelist():
                    data = z.read(tname)
                    img = Image.open(io.BytesIO(data))
                    info['thumbnail_img'] = img
                    break
                    
            # Project settings
            if 'Metadata/project_settings.config' in z.namelist():
                pj = json.loads(z.read('Metadata/project_settings.config').decode('utf-8'))
                info['layer_height'] = str(pj.get('layer_height', 'N/D'))
                info['infill_pattern'] = str(pj.get('sparse_infill_pattern', 'N/D'))
                info['infill_density'] = str(pj.get('sparse_infill_density', 'N/D'))
                info['wall_loops'] = str(pj.get('wall_loops', 'N/D'))
                
                colors = pj.get('filament_colour', [])
                types = pj.get('filament_type', [])
                fil_list = []
                for i, c in enumerate(colors):
                    t = types[i] if i < len(types) else 'PLA'
                    fil_list.append({'color': c, 'type': t, 'slot': i + 1})
                info['filaments'] = fil_list

            # Model settings
            if 'Metadata/model_settings.config' in z.namelist():
                cfg_txt = z.read('Metadata/model_settings.config').decode('utf-8')
                info['is_seq_print'] = 'print_sequence' in cfg_txt and 'by object' in cfg_txt
                
                cfg = ET.fromstring(cfg_txt)
                objs = cfg.findall('object')
                info['object_count'] = len(objs)
                
            # Plate json se presente
            if 'Metadata/plate_1.json' in z.namelist():
                try:
                    pjson = json.loads(z.read('Metadata/plate_1.json').decode('utf-8'))
                    info['bed_type'] = pjson.get('bed_type', 'supertack_plate')
                    if pjson.get('is_seq_print'):
                        info['is_seq_print'] = True
                except Exception:
                    pass
    except Exception as e:
        print(f"Errore lettura metadati da {filepath}: {e}")
    return info

def get_plate_grid_offset(plate_index_1based):
    idx = plate_index_1based - 1
    col = idx % 3
    row = idx // 3
    return (col * BAMBU_PLATE_SPACING_X, -row * BAMBU_PLATE_SPACING_Y)

def perform_merge(file_list, output_path, opt_match_filaments=True, opt_object_overrides=True, opt_preserve_seq=True):
    if len(file_list) < 2:
        raise ValueError("Seleziona almeno 2 file .3mf da unire.")

    base_file = file_list[0]
    with zipfile.ZipFile(base_file, 'r') as z_base:
        base_proj_settings = json.loads(z_base.read('Metadata/project_settings.config').decode('utf-8'))
        
        ET.register_namespace('', 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02')
        ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
        
        tree_model = ET.fromstring(z_base.read('3D/3dmodel.model'))
        res_model = tree_model.find('m:resources', ns)
        build_model = tree_model.find('m:build', ns)
        tree_cfg = ET.fromstring(z_base.read('Metadata/model_settings.config'))
        
        cut_info = None
        if 'Metadata/cut_information.xml' in z_base.namelist():
            cut_info = ET.fromstring(z_base.read('Metadata/cut_information.xml'))
        else:
            cut_info = ET.Element('objects')
            
        layer_heights_lines = []
        if 'Metadata/layer_heights_profile.txt' in z_base.namelist():
            layer_heights_lines = z_base.read('Metadata/layer_heights_profile.txt').decode('utf-8').splitlines()

        fil_sequence = {}
        if 'Metadata/filament_sequence.json' in z_base.namelist():
            try:
                fil_sequence = json.loads(z_base.read('Metadata/filament_sequence.json').decode('utf-8'))
            except Exception:
                fil_sequence = {}
        if 'plate_1' not in fil_sequence:
            fil_sequence['plate_1'] = {"nozzle_sequence":[], "optimal_assignment":[], "sequence":[]}

        base_fil_colors = base_proj_settings.get('filament_colour', [])
        extra_files_to_write = {}
        
        for item in z_base.infolist():
            fname = item.filename
            if fname not in ('3D/3dmodel.model', 'Metadata/model_settings.config',
                             'Metadata/cut_information.xml', 'Metadata/filament_sequence.json',
                             'Metadata/layer_heights_profile.txt'):
                extra_files_to_write[fname] = z_base.read(fname)

        existing_obj_ids = [int(o.attrib['id']) for o in res_model.findall('m:object', ns)]
        max_object_id = max(existing_obj_ids) if existing_obj_ids else 0
        
        existing_part_ids = []
        for p in tree_cfg.findall('.//part'):
            if 'id' in p.attrib:
                existing_part_ids.append(int(p.attrib['id']))
        max_part_id = max(existing_part_ids) if existing_part_ids else 0

        current_plates_count = len(tree_cfg.findall('plate'))
        
        for file_idx, next_filepath in enumerate(file_list[1:], start=2):
            with zipfile.ZipFile(next_filepath, 'r') as z_next:
                next_proj_settings = json.loads(z_next.read('Metadata/project_settings.config').decode('utf-8'))
                next_tree_model = ET.fromstring(z_next.read('3D/3dmodel.model'))
                next_res_model = next_tree_model.find('m:resources', ns)
                next_build_model = next_tree_model.find('m:build', ns)
                next_tree_cfg = ET.fromstring(z_next.read('Metadata/model_settings.config'))
                
                # Calcolo override
                process_overrides = {}
                if opt_object_overrides:
                    for k in OBJECT_OVERRIDE_KEYS:
                        v_base = base_proj_settings.get(k)
                        v_next = next_proj_settings.get(k)
                        if v_next is not None and v_next != v_base:
                            if isinstance(v_next, list):
                                process_overrides[k] = str(v_next[0])
                            else:
                                process_overrides[k] = str(v_next)
                
                id_offset = ((max_object_id // 100) + 1) * 100
                part_offset = ((max_part_id // 100) + 1) * 100
                id_map = {}
                
                next_fil_colors = next_proj_settings.get('filament_colour', [])
                extruder_map = {}
                if opt_match_filaments:
                    for slot_idx, col in enumerate(next_fil_colors, start=1):
                        norm_col = col.upper().strip()
                        for b_idx, b_col in enumerate(base_fil_colors, start=1):
                            if b_col.upper().strip() == norm_col:
                                extruder_map[str(slot_idx)] = str(b_idx)
                                break

                # Aggiungi oggetti 3D
                for obj in next_res_model.findall('m:object', ns):
                    old_id = int(obj.attrib['id'])
                    new_id = old_id + id_offset
                    id_map[str(old_id)] = str(new_id)
                    obj.attrib['id'] = str(new_id)
                    
                    for comp in obj.findall('m:components/m:component', ns):
                        old_cid = comp.attrib['objectid']
                        comp.attrib['objectid'] = str(int(old_cid) + id_offset)
                        
                    res_model.append(obj)
                    if new_id > max_object_id:
                        max_object_id = new_id

                new_plate_id = current_plates_count + 1
                grid_off_x, grid_off_y = get_plate_grid_offset(new_plate_id)

                for item in next_build_model.findall('m:item', ns):
                    old_oid = item.attrib['objectid']
                    new_oid = id_map.get(old_oid, str(int(old_oid) + id_offset))
                    item.attrib['objectid'] = new_oid
                    
                    tf_parts = item.attrib.get('transform', '').split()
                    if len(tf_parts) == 12:
                        tx = float(tf_parts[9]) + grid_off_x
                        ty = float(tf_parts[10]) + grid_off_y
                        tf_parts[9] = f"{tx:.6f}".rstrip('0').rstrip('.')
                        tf_parts[10] = f"{ty:.6f}".rstrip('0').rstrip('.')
                        item.attrib['transform'] = " ".join(tf_parts)
                        
                    build_model.append(item)

                # Oggetti config
                for obj in next_tree_cfg.findall('object'):
                    old_id = obj.attrib['id']
                    new_id = id_map.get(old_id, str(int(old_id) + id_offset))
                    obj.attrib['id'] = new_id
                    
                    for part in obj.findall('part'):
                        if 'id' in part.attrib:
                            np_id = int(part.attrib['id']) + part_offset
                            part.attrib['id'] = str(np_id)
                            if np_id > max_part_id:
                                max_part_id = np_id
                                
                    for meta in obj.findall('metadata'):
                        if meta.attrib.get('key') == 'extruder':
                            old_ext = meta.attrib.get('value')
                            if old_ext in extruder_map:
                                meta.attrib['value'] = extruder_map[old_ext]

                    existing_keys = {m.attrib.get('key') for m in obj.findall('metadata') if 'key' in m.attrib}
                    for ok, ov in process_overrides.items():
                        if ok not in existing_keys:
                            m = ET.Element('metadata')
                            m.attrib['key'] = ok
                            m.attrib['value'] = str(ov)
                            obj.append(m)
                            
                    tree_cfg.append(obj)

                # Piatti
                next_plates = next_tree_cfg.findall('plate')
                for p_elem in next_plates:
                    current_plates_count += 1
                    assigned_plate_num = current_plates_count
                    
                    for meta in p_elem.findall('metadata'):
                        k = meta.attrib.get('key')
                        if k == 'plater_id':
                            meta.attrib['value'] = str(assigned_plate_num)
                        elif k == 'thumbnail_file':
                            meta.attrib['value'] = f"Metadata/plate_{assigned_plate_num}.png"
                        elif k == 'thumbnail_no_light_file':
                            meta.attrib['value'] = f"Metadata/plate_no_light_{assigned_plate_num}.png"
                        elif k == 'top_file':
                            meta.attrib['value'] = f"Metadata/top_{assigned_plate_num}.png"
                        elif k == 'pick_file':
                            meta.attrib['value'] = f"Metadata/pick_{assigned_plate_num}.png"
                        elif k == 'print_sequence' and not opt_preserve_seq:
                            # Se l'utente non vuole preservare la sequenza
                            meta.attrib['value'] = 'by layer'

                    for inst in p_elem.findall('model_instance'):
                        for meta in inst.findall('metadata'):
                            if meta.attrib.get('key') == 'object_id':
                                old_oid = meta.attrib.get('value')
                                meta.attrib['value'] = id_map.get(old_oid, str(int(old_oid) + id_offset))
                                
                    tree_cfg.append(p_elem)
                    
                    thumb_patterns = [
                        ('Metadata/plate_1.png', f"Metadata/plate_{assigned_plate_num}.png"),
                        ('Metadata/plate_1_small.png', f"Metadata/plate_{assigned_plate_num}_small.png"),
                        ('Metadata/plate_no_light_1.png', f"Metadata/plate_no_light_{assigned_plate_num}.png"),
                        ('Metadata/top_1.png', f"Metadata/top_{assigned_plate_num}.png"),
                        ('Metadata/pick_1.png', f"Metadata/pick_{assigned_plate_num}.png"),
                    ]
                    for orig_thumb, target_thumb in thumb_patterns:
                        if orig_thumb in z_next.namelist():
                            extra_files_to_write[target_thumb] = z_next.read(orig_thumb)
                            
                    fil_sequence[f"plate_{assigned_plate_num}"] = {"nozzle_sequence":[], "optimal_assignment":[], "sequence":[]}
                    if 'Metadata/filament_sequence.json' in z_next.namelist():
                        try:
                            nfs = json.loads(z_next.read('Metadata/filament_sequence.json').decode('utf-8'))
                            if 'plate_1' in nfs:
                                fil_sequence[f"plate_{assigned_plate_num}"] = nfs['plate_1']
                        except Exception:
                            pass

                next_assemble = next_tree_cfg.find('assemble')
                base_assemble = tree_cfg.find('assemble')
                if next_assemble is not None and base_assemble is not None:
                    for asm in next_assemble.findall('assemble_item'):
                        old_oid = asm.attrib.get('object_id')
                        if old_oid:
                            asm.attrib['object_id'] = id_map.get(old_oid, str(int(old_oid) + id_offset))
                        base_assemble.append(asm)

                if 'Metadata/cut_information.xml' in z_next.namelist():
                    next_cut = ET.fromstring(z_next.read('Metadata/cut_information.xml'))
                    for obj in next_cut.findall('object'):
                        old_oid = obj.attrib.get('id')
                        obj.attrib['id'] = id_map.get(old_oid, str(int(old_oid) + id_offset))
                        cut_info.append(obj)

                if 'Metadata/layer_heights_profile.txt' in z_next.namelist():
                    for line in z_next.read('Metadata/layer_heights_profile.txt').decode('utf-8').splitlines():
                        if line.startswith('object_id='):
                            parts = line.split('|', 1)
                            old_oid = parts[0].split('=')[1]
                            new_oid = id_map.get(old_oid, str(int(old_oid) + id_offset))
                            layer_heights_lines.append(f"object_id={new_oid}|{parts[1]}")

                for item in z_next.infolist():
                    if item.filename.startswith('Auxiliaries/'):
                        if item.filename not in extra_files_to_write:
                            extra_files_to_write[item.filename] = z_next.read(item.filename)

        final_3dmodel_bytes = ET.tostring(tree_model, encoding='utf-8', xml_declaration=True)
        final_cfg_bytes = ET.tostring(tree_cfg, encoding='utf-8', xml_declaration=True)
        final_cut_bytes = ET.tostring(cut_info, encoding='utf-8', xml_declaration=True) if len(cut_info) > 0 else None
        final_fil_seq_bytes = json.dumps(fil_sequence).encode('utf-8')
        final_layer_heights_bytes = "\n".join(layer_heights_lines).encode('utf-8') if layer_heights_lines else None

        with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            for fname, fbytes in extra_files_to_write.items():
                zout.writestr(fname, fbytes)
            zout.writestr('3D/3dmodel.model', final_3dmodel_bytes)
            zout.writestr('Metadata/model_settings.config', final_cfg_bytes)
            zout.writestr('Metadata/filament_sequence.json', final_fil_seq_bytes)
            if final_cut_bytes:
                zout.writestr('Metadata/cut_information.xml', final_cut_bytes)
            if final_layer_heights_bytes:
                zout.writestr('Metadata/layer_heights_profile.txt', final_layer_heights_bytes)

    return current_plates_count


class PlateCard(ctk.CTkFrame):
    """Scheda grafica per ogni piatto 3MF inserito"""
    def __init__(self, master, plate_index, meta_info, on_move_up, on_move_down, on_remove):
        super().__init__(master, corner_radius=10, fg_color=("#2B2B2B", "#222222"), border_width=1, border_color="#3A3A3A")
        self.plate_index = plate_index
        self.meta = meta_info

        # Layout a griglia
        self.grid_columnconfigure(1, weight=1)

        # Colonna 0: Miniatura
        thumb_frame = ctk.CTkFrame(self, width=72, height=72, corner_radius=8, fg_color="#181818")
        thumb_frame.grid(row=0, column=0, rowspan=2, padx=12, pady=10)
        thumb_frame.pack_propagate(False)

        if self.meta.get('thumbnail_img'):
            try:
                ctk_img = ctk.CTkImage(light_image=self.meta['thumbnail_img'], dark_image=self.meta['thumbnail_img'], size=(64, 64))
                img_lbl = ctk.CTkLabel(thumb_frame, text="", image=ctk_img)
                img_lbl.pack(expand=True)
            except Exception:
                ctk.CTkLabel(thumb_frame, text="3D", font=("Segoe UI", 16, "bold"), text_color="#777777").pack(expand=True)
        else:
            ctk.CTkLabel(thumb_frame, text="3D", font=("Segoe UI", 16, "bold"), text_color="#777777").pack(expand=True)

        # Colonna 1: Info e Badges
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="w", padx=4, pady=(10, 2))

        # Titolo e Piatto
        badge_text = f"PIATTO {plate_index}"
        badge_color = "#008855" if plate_index == 1 else "#1E6EA7"
        plate_badge = ctk.CTkLabel(info_frame, text=badge_text, font=("Segoe UI", 10, "bold"),
                                   fg_color=badge_color, text_color="white", corner_radius=5, padx=6, pady=2)
        plate_badge.pack(side="left", padx=(0, 8))

        name_lbl = ctk.CTkLabel(info_frame, text=self.meta['filename'], font=("Segoe UI", 12, "bold"))
        name_lbl.pack(side="left")

        # Seconda riga: Badges parametri
        tags_frame = ctk.CTkFrame(self, fg_color="transparent")
        tags_frame.grid(row=1, column=1, sticky="w", padx=4, pady=(0, 10))

        # Badge Layer Height
        lh_val = self.meta.get('layer_height', 'N/D')
        self._add_tag(tags_frame, f"📐 {lh_val} mm", "#333333", "#CCCCCC")

        # Badge Sequenza
        if self.meta.get('is_seq_print'):
            self._add_tag(tags_frame, "⚡ Stampa x Oggetto", "#7A4100", "#FFAA44")
        else:
            self._add_tag(tags_frame, "🧱 Stampa x Livello", "#2A2A2A", "#AAAAAA")

        # Badge Infill
        infill_val = self.meta.get('infill_pattern', 'N/D')
        if infill_val != 'N/D':
            self._add_tag(tags_frame, f"🌀 {infill_val}", "#2A2A2A", "#AAAAAA")

        # Badge Muri/Pareti
        walls_val = self.meta.get('wall_loops', 'N/D')
        if walls_val != 'N/D':
            self._add_tag(tags_frame, f"🛡️ {walls_val} muri", "#2A2A2A", "#AAAAAA")

        # Badge Filamenti
        fils = self.meta.get('filaments', [])
        if fils:
            fil_frame = ctk.CTkFrame(tags_frame, fg_color="transparent")
            fil_frame.pack(side="left", padx=4)
            for f in fils[:4]:
                color_dot = ctk.CTkLabel(fil_frame, text="  ", font=("Segoe UI", 7),
                                         fg_color=f['color'], corner_radius=4, width=12, height=12)
                color_dot.pack(side="left", padx=1)

        # Colonna 2: Pulsanti di controllo
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=0, column=2, rowspan=2, padx=10, pady=8)

        btn_up = ctk.CTkButton(actions_frame, text="▲", width=28, height=26, font=("Segoe UI", 11),
                               fg_color="#3A3A3A", hover_color="#505050", command=on_move_up)
        btn_up.pack(side="top", pady=2)

        btn_down = ctk.CTkButton(actions_frame, text="▼", width=28, height=26, font=("Segoe UI", 11),
                                 fg_color="#3A3A3A", hover_color="#505050", command=on_move_down)
        btn_down.pack(side="top", pady=2)

        btn_del = ctk.CTkButton(actions_frame, text="✕", width=28, height=26, font=("Segoe UI", 11, "bold"),
                                fg_color="#661111", hover_color="#991111", command=on_remove)
        btn_del.pack(side="top", pady=2)

    def _add_tag(self, parent, text, bg_color, text_color):
        lbl = ctk.CTkLabel(parent, text=text, font=("Segoe UI", 10),
                           fg_color=bg_color, text_color=text_color, corner_radius=4, padx=5, pady=1)
        lbl.pack(side="left", padx=(0, 4))


class BambuPlateMergerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Bambu Multi-Plate Studio — Unione Piatti 3MF")
        self.geometry("820x680")
        self.minsize(740, 560)

        self.bambu_path = find_bambu_studio_path()
        self.plate_files = []
        self.plate_metadata_cache = {}
        self.last_merged_file = None

        self._build_ui()
        self._load_default_folder_files()

    def _build_ui(self):
        # 1. Header
        header = ctk.CTkFrame(self, corner_radius=0, fg_color=("#1F1F1F", "#181818"), height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=12)

        title_lbl = ctk.CTkLabel(title_frame, text="Bambu Multi-Plate Studio", font=("Segoe UI", 18, "bold"), text_color="#00C055")
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(title_frame, text="Unisci più piatti 3MF preservando altezze layer, sequenze e impostazioni differenti",
                               font=("Segoe UI", 11), text_color="#999999")
        sub_lbl.pack(anchor="w")

        # Info Bambu Studio installato
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.pack(side="right", padx=20, pady=14)
        if self.bambu_path:
            b_lbl = ctk.CTkLabel(status_frame, text="✓ Bambu Studio rilevato", font=("Segoe UI", 10, "bold"), text_color="#00C055")
            b_lbl.pack(anchor="e")
        else:
            b_lbl = ctk.CTkLabel(status_frame, text="Bambu Studio non rilevato nel PATH", font=("Segoe UI", 10), text_color="#888888")
            b_lbl.pack(anchor="e")

        # 2. Main Container (Corpo centrale)
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=15)

        # Barra superiore azioni lista
        bar_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        bar_frame.pack(fill="x", pady=(0, 8))

        lbl_plates = ctk.CTkLabel(bar_frame, text="Elenco Piatti da Unire (Ordinati per Piatto 1, 2, ...)",
                                  font=("Segoe UI", 13, "bold"))
        lbl_plates.pack(side="left")

        btn_add = ctk.CTkButton(bar_frame, text="+ Aggiungi File .3MF", font=("Segoe UI", 12, "bold"),
                                fg_color="#008855", hover_color="#00AA66", command=self.add_files, height=32)
        btn_add.pack(side="right")

        btn_clear = ctk.CTkButton(bar_frame, text="Svuota", font=("Segoe UI", 11),
                                  fg_color="#333333", hover_color="#444444", width=70, command=self.clear_all, height=32)
        btn_clear.pack(side="right", padx=(0, 8))

        # Scrollable Frame per i piatti
        self.scroll_plates = ctk.CTkScrollableFrame(main_container, corner_radius=10, fg_color=("#1A1A1A", "#141414"), border_width=1, border_color="#2A2A2A")
        self.scroll_plates.pack(fill="both", expand=True)

        # 3. Pannello Opzioni Essenziali (in basso)
        opt_panel = ctk.CTkFrame(self, corner_radius=10, fg_color=("#222222", "#1B1B1B"), border_width=1, border_color="#2E2E2E")
        opt_panel.pack(fill="x", padx=20, pady=(0, 15))

        opt_title = ctk.CTkLabel(opt_panel, text="Opzioni Essenziali di Unione", font=("Segoe UI", 11, "bold"), text_color="#00C055")
        opt_title.pack(anchor="w", padx=15, pady=(8, 4))

        opt_grid = ctk.CTkFrame(opt_panel, fg_color="transparent")
        opt_grid.pack(fill="x", padx=15, pady=(0, 10))

        self.var_match_filaments = ctk.BooleanVar(value=True)
        chk_filaments = ctk.CTkCheckBox(opt_grid, text="Riconcilia filamenti uguali (es. unisci slot con stesso colore)",
                                        variable=self.var_match_filaments, font=("Segoe UI", 11))
        chk_filaments.grid(row=0, column=0, sticky="w", padx=(0, 20), pady=3)

        self.var_object_overrides = ctk.BooleanVar(value=True)
        chk_overrides = ctk.CTkCheckBox(opt_grid, text="Conserva layer height e impostazioni differenti per oggetto",
                                        variable=self.var_object_overrides, font=("Segoe UI", 11))
        chk_overrides.grid(row=0, column=1, sticky="w", pady=3)

        self.var_preserve_seq = ctk.BooleanVar(value=True)
        chk_seq = ctk.CTkCheckBox(opt_grid, text="Conserva sequenza 'Stampa per Oggetto' (By Object) per piatto",
                                  variable=self.var_preserve_seq, font=("Segoe UI", 11))
        chk_seq.grid(row=1, column=0, sticky="w", padx=(0, 20), pady=3)

        self.var_open_bambu = ctk.BooleanVar(value=True if self.bambu_path else False)
        chk_open = ctk.CTkCheckBox(opt_grid, text="Apri automaticamente in Bambu Studio al completamento",
                                   variable=self.var_open_bambu, font=("Segoe UI", 11))
        chk_open.grid(row=1, column=1, sticky="w", pady=3)

        # 4. Action Footer (Pulsante di fusione e barra stato)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 15))

        self.btn_merge = ctk.CTkButton(
            footer, text="🚀 Unisci Piatti in un Unico File 3MF",
            font=("Segoe UI", 14, "bold"), fg_color="#00AE42", hover_color="#00D250",
            height=46, command=self.start_merge_thread
        )
        self.btn_merge.pack(fill="x")

        self.status_lbl = ctk.CTkLabel(footer, text="Pronto. Aggiungi almeno 2 file 3MF per iniziare.", font=("Segoe UI", 11), text_color="#777777")
        self.status_lbl.pack(anchor="w", pady=(6, 0))

    def _load_default_folder_files(self):
        """Carica automaticamente i file passati come argomenti o quelli presenti nella cartella"""
        args_files = [arg for arg in sys.argv[1:] if arg.lower().endswith('.3mf') and os.path.isfile(arg)]
        if args_files:
            for f in args_files:
                self.add_single_file(f, refresh=False)
        else:
            cwd = os.getcwd()
            sample1 = os.path.join(cwd, 'manico - Copia.3mf')
            sample2 = os.path.join(cwd, 'sfere - Copia.3mf')
            if os.path.isfile(sample1):
                self.add_single_file(sample1, refresh=False)
            if os.path.isfile(sample2):
                self.add_single_file(sample2, refresh=False)
        self.refresh_cards()

    def add_files(self):
        selected = filedialog.askopenfilenames(
            title="Seleziona file .3mf da unire",
            filetypes=[("Progetti Bambu / 3MF", "*.3mf"), ("Tutti i file", "*.*")]
        )
        if selected:
            for s in selected:
                if s not in self.plate_files:
                    self.add_single_file(s, refresh=False)
            self.refresh_cards()

    def add_single_file(self, filepath, refresh=True):
        if filepath not in self.plate_files:
            self.plate_files.append(filepath)
            if filepath not in self.plate_metadata_cache:
                self.plate_metadata_cache[filepath] = extract_plate_metadata(filepath)
        if refresh:
            self.refresh_cards()

    def clear_all(self):
        self.plate_files.clear()
        self.refresh_cards()

    def move_up(self, index):
        if index > 0:
            self.plate_files[index], self.plate_files[index - 1] = self.plate_files[index - 1], self.plate_files[index]
            self.refresh_cards()

    def move_down(self, index):
        if index < len(self.plate_files) - 1:
            self.plate_files[index], self.plate_files[index + 1] = self.plate_files[index + 1], self.plate_files[index]
            self.refresh_cards()

    def remove_file(self, index):
        if 0 <= index < len(self.plate_files):
            del self.plate_files[index]
            self.refresh_cards()

    def refresh_cards(self):
        # Pulisci scrollable frame
        for child in self.scroll_plates.winfo_children():
            child.destroy()

        if not self.plate_files:
            empty_lbl = ctk.CTkLabel(
                self.scroll_plates,
                text="Trascina qui i tuoi file 3MF oppure clicca su '+ Aggiungi File .3MF'",
                font=("Segoe UI", 12), text_color="#555555"
            )
            empty_lbl.pack(pady=40)
            self.btn_merge.configure(state="disabled", fg_color="#333333")
            self.status_lbl.configure(text="Nessun file selezionato. Aggiungi almeno 2 file 3MF.", text_color="#777777")
            return

        for idx, fpath in enumerate(self.plate_files):
            meta = self.plate_metadata_cache.get(fpath, extract_plate_metadata(fpath))
            card = PlateCard(
                self.scroll_plates,
                plate_index=idx + 1,
                meta_info=meta,
                on_move_up=lambda i=idx: self.move_up(i),
                on_move_down=lambda i=idx: self.move_down(i),
                on_remove=lambda i=idx: self.remove_file(i)
            )
            card.pack(fill="x", pady=4, padx=4)

        if len(self.plate_files) >= 2:
            self.btn_merge.configure(state="normal", fg_color="#00AE42")
            self.status_lbl.configure(
                text=f"Pronto per unire {len(self.plate_files)} piatti in un unico progetto multi-piatto.",
                text_color="#00C055"
            )
        else:
            self.btn_merge.configure(state="disabled", fg_color="#333333")
            self.status_lbl.configure(
                text="Aggiungi almeno un altro file 3MF per procedere all'unione.",
                text_color="#FFAA00"
            )

    def start_merge_thread(self):
        if len(self.plate_files) < 2:
            messagebox.showwarning("Attenzione", "Aggiungi almeno 2 file .3mf da unire.")
            return

        default_dir = os.path.dirname(self.plate_files[0])
        out_path = filedialog.asksaveasfilename(
            title="Salva file 3MF unito",
            initialdir=default_dir,
            initialfile="progetto_unito.3mf",
            defaultextension=".3mf",
            filetypes=[("Bambu 3MF Project", "*.3mf")]
        )
        if not out_path:
            return

        self.btn_merge.configure(state="disabled", text="⏳ Elaborazione in corso...")
        self.status_lbl.configure(text="Unione delle mesh, calcolo degli override e assemblaggio dei piatti...", text_color="#FFAA00")

        threading.Thread(target=self._run_merge, args=(out_path,), daemon=True).start()

    def _run_merge(self, out_path):
        try:
            total_plates = perform_merge(
                self.plate_files,
                out_path,
                opt_match_filaments=self.var_match_filaments.get(),
                opt_object_overrides=self.var_object_overrides.get(),
                opt_preserve_seq=self.var_preserve_seq.get()
            )
            self.last_merged_file = out_path
            self.after(0, lambda: self._on_merge_success(out_path, total_plates))
        except Exception as e:
            self.after(0, lambda: self._on_merge_error(str(e)))

    def _on_merge_success(self, out_path, total_plates):
        self.btn_merge.configure(state="normal", text="🚀 Unisci Piatti in un Unico File 3MF")
        self.status_lbl.configure(
            text=f"✓ Unione completata con successo! {total_plates} piatti salvati in: {os.path.basename(out_path)}",
            text_color="#00C055"
        )

        if self.var_open_bambu.get() and self.bambu_path:
            try:
                subprocess.Popen([self.bambu_path, out_path])
            except Exception as e:
                print(f"Errore apertura Bambu Studio: {e}")

        # Mostra dialog di successo
        msg = f"Il progetto multi-piatto è stato generato con successo!\n\n" \
              f"• Totale Piatti: {total_plates}\n" \
              f"• File salvato: {out_path}\n"
        if self.var_open_bambu.get() and self.bambu_path:
            msg += "\nIl file è stato aperto automaticamente in Bambu Studio."
            
        messagebox.showinfo("Operazione Completata", msg)

    def _on_merge_error(self, err_msg):
        self.btn_merge.configure(state="normal", text="🚀 Unisci Piatti in un Unico File 3MF")
        self.status_lbl.configure(text=f"Errore: {err_msg}", text_color="#FF4444")
        messagebox.showerror("Errore durante l'unione", f"Si è verificato un errore:\n\n{err_msg}")


if __name__ == '__main__':
    app = BambuPlateMergerApp()
    app.mainloop()
