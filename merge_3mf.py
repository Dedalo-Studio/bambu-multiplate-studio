#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bambu Studio / OrcaSlicer Multi-Plate 3MF Merger Tool
=====================================================
Unisce più file .3mf (ciascuno con i propri piatti e impostazioni di stampa)
in un unico file .3mf multi-piatto compatibile al 100% con Bambu Studio e OrcaSlicer.

Caratteristiche:
- Supporta N file .3mf in ingresso
- Preserva le impostazioni specifiche di ogni piatto (es. Stampa per Oggetto / By Object vs By Layer)
- Converte le impostazioni di processo discordanti in override a livello di oggetto (<object>)
  permettendo layer height differenti (es. 0.20mm sul piatto 1 e 0.08mm sul piatto 2),
  diversi infill, velocità, perimetri (muri), supporti e brim
- Calcola e applica la traslazione spaziale dei piatti nella griglia 3D di Bambu Studio (+307.2mm per colonna)
- Risolve le collisioni di ID (mesh, componenti, oggetti e parti)
- Mappa automaticamente i filamenti compatibili (es. slot colore/tipo)
- Preserva profili di altezza layer variabile (layer_heights_profile.txt)
- Preserva e rinomina le miniature di ciascun piatto (plate_1.png, plate_2.png, ecc.)
"""

import os
import sys
import json
import zipfile
import argparse
import xml.etree.ElementTree as ET

# Spaziatura piatti Bambu Studio: letto 256mm + 51.2mm spazio visivo
BAMBU_PLATE_SPACING_X = 307.2
BAMBU_PLATE_SPACING_Y = 307.2

# Parametri di slicing che possono essere sovrascritti a livello di singolo oggetto in Bambu Studio / libslic3r
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

def parse_xml_bytes(b_data):
    return ET.fromstring(b_data)

def get_plate_grid_offset(plate_index_1based):
    """Restituisce (offset_x, offset_y) per il piatto specificato (griglia 3 colonne)"""
    idx = plate_index_1based - 1
    col = idx % 3
    row = idx // 3
    return (col * BAMBU_PLATE_SPACING_X, -row * BAMBU_PLATE_SPACING_Y)

def merge_3mf_files(file_list, output_path, match_filaments=True, verbose=True):
    if len(file_list) < 2:
        raise ValueError("Sono necessari almeno 2 file .3mf per eseguire l'unione.")

    if verbose:
        print(f"=== Avvio unione di {len(file_list)} file .3mf ===")
        for i, f in enumerate(file_list, start=1):
            print(f"  Piatto sorgente {i}: {os.path.basename(f)}")

    # Apriamo il primo file come base
    base_file = file_list[0]
    with zipfile.ZipFile(base_file, 'r') as z_base:
        # Carichiamo configurazioni globali del file base
        base_proj_settings = json.loads(z_base.read('Metadata/project_settings.config').decode('utf-8'))
        
        ET.register_namespace('', 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02')
        ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
        
        tree_model = ET.fromstring(z_base.read('3D/3dmodel.model'))
        res_model = tree_model.find('m:resources', ns)
        build_model = tree_model.find('m:build', ns)
        
        tree_cfg = ET.fromstring(z_base.read('Metadata/model_settings.config'))
        
        # Cut info se presente
        cut_info = None
        if 'Metadata/cut_information.xml' in z_base.namelist():
            cut_info = ET.fromstring(z_base.read('Metadata/cut_information.xml'))
        else:
            cut_info = ET.Element('objects')
            
        # Layer heights profile se presente
        layer_heights_lines = []
        if 'Metadata/layer_heights_profile.txt' in z_base.namelist():
            layer_heights_lines = z_base.read('Metadata/layer_heights_profile.txt').decode('utf-8').splitlines()

        # Filament sequence
        fil_sequence = {}
        if 'Metadata/filament_sequence.json' in z_base.namelist():
            try:
                fil_sequence = json.loads(z_base.read('Metadata/filament_sequence.json').decode('utf-8'))
            except Exception:
                fil_sequence = {}
        if 'plate_1' not in fil_sequence:
            fil_sequence['plate_1'] = {"nozzle_sequence":[], "optimal_assignment":[], "sequence":[]}

        # Mappatura filamenti base
        base_fil_colors = base_proj_settings.get('filament_colour', [])
        base_fil_types = base_proj_settings.get('filament_type', [])
        
        # Manteniamo traccia dei file binari aggiuntivi da scrivere nel nuovo ZIP (immagini, ecc.)
        extra_files_to_write = {}
        
        # Copiamo i file originali del base file
        for item in z_base.infolist():
            fname = item.filename
            if fname not in ('3D/3dmodel.model', 'Metadata/model_settings.config',
                             'Metadata/cut_information.xml', 'Metadata/filament_sequence.json',
                             'Metadata/layer_heights_profile.txt'):
                extra_files_to_write[fname] = z_base.read(fname)

        # Monitor ID massimi usati
        existing_obj_ids = [int(o.attrib['id']) for o in res_model.findall('m:object', ns)]
        max_object_id = max(existing_obj_ids) if existing_obj_ids else 0
        
        existing_part_ids = []
        for p in tree_cfg.findall('.//part'):
            if 'id' in p.attrib:
                existing_part_ids.append(int(p.attrib['id']))
        max_part_id = max(existing_part_ids) if existing_part_ids else 0

        # Quanti piatti ci sono attualmente
        current_plates_count = len(tree_cfg.findall('plate'))
        
        # Iteriamo sui file successivi
        for file_idx, next_filepath in enumerate(file_list[1:], start=2):
            if verbose:
                print(f"\nElaborazione file {file_idx}: {os.path.basename(next_filepath)}")
                
            with zipfile.ZipFile(next_filepath, 'r') as z_next:
                next_proj_settings = json.loads(z_next.read('Metadata/project_settings.config').decode('utf-8'))
                next_tree_model = ET.fromstring(z_next.read('3D/3dmodel.model'))
                next_res_model = next_tree_model.find('m:resources', ns)
                next_build_model = next_tree_model.find('m:build', ns)
                next_tree_cfg = ET.fromstring(z_next.read('Metadata/model_settings.config'))
                
                # Calcola override di processo per questo piatto rispetto al profilo globale base
                process_overrides = {}
                for k in OBJECT_OVERRIDE_KEYS:
                    v_base = base_proj_settings.get(k)
                    v_next = next_proj_settings.get(k)
                    if v_next is not None and v_next != v_base:
                        if isinstance(v_next, list):
                            process_overrides[k] = str(v_next[0])
                        else:
                            process_overrides[k] = str(v_next)
                
                if verbose and process_overrides:
                    print(f"  -> Applicati {len(process_overrides)} parametri di processo specifici per gli oggetti di questo piatto:")
                    for pk, pv in list(process_overrides.items())[:6]:
                        print(f"     * {pk} = {pv}")
                    if len(process_overrides) > 6:
                        print(f"     * ... e altri {len(process_overrides)-6} parametri")

                # Offset ID per evitare collisioni
                id_offset = ((max_object_id // 100) + 1) * 100
                part_offset = ((max_part_id // 100) + 1) * 100
                
                id_map = {}
                
                # Mappatura filamenti
                # Se il file 2 usa un filamento di un certo colore/tipo già presente nel base, mappiamo allo slot base
                next_fil_colors = next_proj_settings.get('filament_colour', [])
                extruder_map = {}
                if match_filaments:
                    for slot_idx, col in enumerate(next_fil_colors, start=1):
                        norm_col = col.upper().strip()
                        # Cerchiamo lo stesso colore nel base
                        found_slot = None
                        for b_idx, b_col in enumerate(base_fil_colors, start=1):
                            if b_col.upper().strip() == norm_col:
                                found_slot = str(b_idx)
                                break
                        if found_slot:
                            extruder_map[str(slot_idx)] = found_slot
                            if verbose:
                                print(f"  -> Mappato estrusore {slot_idx} ({norm_col}) allo slot {found_slot} del progetto base")

                # Aggiungiamo le risorse 3D
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

                # Offset spaziale per questo piatto
                new_plate_id = current_plates_count + 1
                grid_off_x, grid_off_y = get_plate_grid_offset(new_plate_id)
                if verbose:
                    print(f"  -> Nuovo piatto assegnato: ID {new_plate_id} (offset griglia X: +{grid_off_x:.1f}mm, Y: {grid_off_y:.1f}mm)")

                # Build items
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

                # model_settings.config: oggetti
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
                                
                    # Mappa estrusore se configurato
                    for meta in obj.findall('metadata'):
                        if meta.attrib.get('key') == 'extruder':
                            old_ext = meta.attrib.get('value')
                            if old_ext in extruder_map:
                                meta.attrib['value'] = extruder_map[old_ext]

                    # Inietta i parametri di processo discordanti come override
                    existing_keys = {m.attrib.get('key') for m in obj.findall('metadata') if 'key' in m.attrib}
                    for ok, ov in process_overrides.items():
                        if ok not in existing_keys:
                            m = ET.Element('metadata')
                            m.attrib['key'] = ok
                            m.attrib['value'] = str(ov)
                            obj.append(m)
                            
                    tree_cfg.append(obj)

                # model_settings.config: piatti
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
                            
                    for inst in p_elem.findall('model_instance'):
                        for meta in inst.findall('metadata'):
                            if meta.attrib.get('key') == 'object_id':
                                old_oid = meta.attrib.get('value')
                                meta.attrib['value'] = id_map.get(old_oid, str(int(old_oid) + id_offset))
                                
                    tree_cfg.append(p_elem)
                    
                    # Miniature corrispondenti
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
                            
                    # Aggiorna filament sequence
                    fil_sequence[f"plate_{assigned_plate_num}"] = {"nozzle_sequence":[], "optimal_assignment":[], "sequence":[]}
                    if 'Metadata/filament_sequence.json' in z_next.namelist():
                        try:
                            nfs = json.loads(z_next.read('Metadata/filament_sequence.json').decode('utf-8'))
                            if 'plate_1' in nfs:
                                fil_sequence[f"plate_{assigned_plate_num}"] = nfs['plate_1']
                        except Exception:
                            pass

                # Assemble items
                next_assemble = next_tree_cfg.find('assemble')
                base_assemble = tree_cfg.find('assemble')
                if next_assemble is not None and base_assemble is not None:
                    for asm in next_assemble.findall('assemble_item'):
                        old_oid = asm.attrib.get('object_id')
                        if old_oid:
                            asm.attrib['object_id'] = id_map.get(old_oid, str(int(old_oid) + id_offset))
                        base_assemble.append(asm)

                # Cut information
                if 'Metadata/cut_information.xml' in z_next.namelist():
                    next_cut = ET.fromstring(z_next.read('Metadata/cut_information.xml'))
                    for obj in next_cut.findall('object'):
                        old_oid = obj.attrib.get('id')
                        obj.attrib['id'] = id_map.get(old_oid, str(int(old_oid) + id_offset))
                        cut_info.append(obj)

                # Layer heights profile
                if 'Metadata/layer_heights_profile.txt' in z_next.namelist():
                    for line in z_next.read('Metadata/layer_heights_profile.txt').decode('utf-8').splitlines():
                        if line.startswith('object_id='):
                            parts = line.split('|', 1)
                            old_oid = parts[0].split('=')[1]
                            new_oid = id_map.get(old_oid, str(int(old_oid) + id_offset))
                            layer_heights_lines.append(f"object_id={new_oid}|{parts[1]}")

                # Immagini ausiliarie
                for item in z_next.infolist():
                    if item.filename.startswith('Auxiliaries/'):
                        if item.filename not in extra_files_to_write:
                            extra_files_to_write[item.filename] = z_next.read(item.filename)

        # Genera XML finali
        final_3dmodel_bytes = ET.tostring(tree_model, encoding='utf-8', xml_declaration=True)
        final_cfg_bytes = ET.tostring(tree_cfg, encoding='utf-8', xml_declaration=True)
        final_cut_bytes = ET.tostring(cut_info, encoding='utf-8', xml_declaration=True) if len(cut_info) > 0 else None
        final_fil_seq_bytes = json.dumps(fil_sequence).encode('utf-8')
        final_layer_heights_bytes = "\n".join(layer_heights_lines).encode('utf-8') if layer_heights_lines else None

        # Scrittura archivio ZIP .3mf finale
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

    if verbose:
        print(f"\n[OK] File multi-piatto generato con successo: '{output_path}'")
        print(f"     Totale piatti combinati: {current_plates_count}")

def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("Bambu Studio - Unione Piatti 3MF")
    root.geometry("640x520")
    root.minsize(500, 400)

    files_list = []

    def update_listbox():
        listbox.delete(0, tk.END)
        for i, f in enumerate(files_list, start=1):
            listbox.insert(tk.END, f"Piatto {i}: {os.path.basename(f)}  ({f})")

    def add_files():
        selected = filedialog.askopenfilenames(
            title="Seleziona file .3mf da unire",
            filetypes=[("Bambu 3MF Project", "*.3mf"), ("Tutti i file", "*.*")]
        )
        if selected:
            for s in selected:
                if s not in files_list:
                    files_list.append(s)
            update_listbox()

    def remove_selected():
        sel = listbox.curselection()
        if sel:
            idx = sel[0]
            del files_list[idx]
            update_listbox()

    def move_up():
        sel = listbox.curselection()
        if sel and sel[0] > 0:
            idx = sel[0]
            files_list[idx], files_list[idx - 1] = files_list[idx - 1], files_list[idx]
            update_listbox()
            listbox.selection_set(idx - 1)

    def move_down():
        sel = listbox.curselection()
        if sel and sel[0] < len(files_list) - 1:
            idx = sel[0]
            files_list[idx], files_list[idx + 1] = files_list[idx + 1], files_list[idx]
            update_listbox()
            listbox.selection_set(idx + 1)

    def execute_merge():
        if len(files_list) < 2:
            messagebox.showwarning("Attenzione", "Aggiungi almeno 2 file .3mf da unire.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Salva file 3MF unito",
            defaultextension=".3mf",
            filetypes=[("Bambu 3MF Project", "*.3mf")],
            initialfile="progetto_completo_multi_piatto.3mf"
        )
        if not out_path:
            return

        try:
            merge_3mf_files(files_list, out_path, match_filaments=True, verbose=False)
            messagebox.showinfo("Successo", f"File multi-piatto creato con successo!\n\nSalvato in:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Errore", f"Si è verificato un errore durante l'unione:\n{str(e)}")

    # Frame superiore: istruzioni
    top_frame = tk.Frame(root, padx=15, pady=10)
    top_frame.pack(fill=tk.X)

    title_label = tk.Label(top_frame, text="Unione Multi-Piatto 3MF per Bambu Studio", font=("Segoe UI", 12, "bold"))
    title_label.pack(anchor="w")

    desc_label = tk.Label(
        top_frame,
        text="Aggiungi i file .3mf da unire. Ogni file diventerà un piatto separato\nmantenendo le sue impostazioni di stampa, layer height e sequenza (es. By Object).",
        justify=tk.LEFT, fg="#444444"
    )
    desc_label.pack(anchor="w", pady=(3, 0))

    # Frame centrale: lista e pulsanti laterali
    center_frame = tk.Frame(root, padx=15, pady=5)
    center_frame.pack(fill=tk.BOTH, expand=True)

    listbox_frame = tk.Frame(center_frame)
    listbox_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
    listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, selectmode=tk.SINGLE, font=("Segoe UI", 9))
    scrollbar.config(command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    btn_frame = tk.Frame(center_frame, padx=10)
    btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

    btn_add = tk.Button(btn_frame, text="Aggiungi File...", width=14, command=add_files)
    btn_add.pack(pady=4)

    btn_remove = tk.Button(btn_frame, text="Rimuovi", width=14, command=remove_selected)
    btn_remove.pack(pady=4)

    btn_up = tk.Button(btn_frame, text="Sposta Su", width=14, command=move_up)
    btn_up.pack(pady=4)

    btn_down = tk.Button(btn_frame, text="Sposta Giù", width=14, command=move_down)
    btn_down.pack(pady=4)

    # Frame inferiore: azione
    bottom_frame = tk.Frame(root, padx=15, pady=15)
    bottom_frame.pack(fill=tk.X)

    btn_merge = tk.Button(
        bottom_frame, text="Unisci Piatti in un Unico 3MF",
        font=("Segoe UI", 10, "bold"), bg="#009688", fg="white",
        padx=10, pady=8, command=execute_merge
    )
    btn_merge.pack(fill=tk.X)

    # Inizializziamo con i file presenti nella cartella se ci sono
    cwd = os.getcwd()
    sample1 = os.path.join(cwd, 'manico - Copia.3mf')
    sample2 = os.path.join(cwd, 'sfere - Copia.3mf')
    if os.path.exists(sample1):
        files_list.append(sample1)
    if os.path.exists(sample2):
        files_list.append(sample2)
    update_listbox()

    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Unisce più file 3MF in un unico file multi-piatto per Bambu Studio.")
    parser.add_argument("files", nargs="*", help="File .3mf da unire (in ordine di piatto)")
    parser.add_argument("-o", "--output", default="progetto_unito.3mf", help="Percorso del file .3mf risultante")
    parser.add_argument("--no-match-filaments", action="store_true", help="Non mappare automaticamente i colori filamento uguali")
    parser.add_argument("--gui", action="store_true", help="Avvia l'interfaccia grafica interattiva")

    args = parser.parse_args()

    if args.gui or len(args.files) == 0:
        if len(args.files) == 0 and not args.gui:
            # Se avviato senza argomenti e c'è un terminale o doppio clic
            launch_gui()
            return
        launch_gui()
    else:
        merge_3mf_files(
            args.files,
            args.output,
            match_filaments=not args.no_match_filaments,
            verbose=True
        )

if __name__ == '__main__':
    main()
