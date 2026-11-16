"""Offline Word evidence export from Console Capture run summary files."""
import json
from pathlib import Path
from datetime import datetime
from docx import Document
from PIL import Image
from io import BytesIO
from copy import deepcopy
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT


def read_run(folder):
    folder = Path(folder).resolve()
    manifest = folder / 'summary.json'
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(data.get('results'), list):
        raise ValueError(f'Invalid run manifest: {manifest}')
    return folder, data


def safe_image_path(folder, name):
    if not name or not isinstance(name, str):
        raise ValueError('Missing image path')
    path = (folder / name.replace('\\', '/')).resolve()
    if not path.is_relative_to(folder.resolve()) or path.suffix.lower() != '.png':
        raise ValueError(f'Invalid image path: {name}')
    return path


def _format_report_timestamp(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z','+00:00')).strftime('%d-%m-%y (%H:%M)')
    except (TypeError, ValueError):
        return str(value or '—')


def add_run(doc, folder, data, index, combined, include_text=False):
    if combined and index:
        doc.add_page_break()
    device = data.get('device') or folder.name
    doc.add_heading(f'Device: {device}', level=1)
    details = doc.add_table(rows=0, cols=2)
    details.style = 'Table Grid'
    details.alignment = WD_TABLE_ALIGNMENT.CENTER
    for label, key in [('Command group','group'),('CLI hostname','cli_hostname'),('COM port','com_port'),('Started','started_at'),('Completed','completed_at')]:
        cells=details.add_row().cells
        cells[0].text=label
        cells[1].text=_format_report_timestamp(data.get(key)) if key in ('started_at','completed_at') else str(data.get(key) or '—')
    results=sorted(enumerate(data['results']), key=lambda p: (p[1].get('order', p[0]+1),p[0]))
    for idx, (_, record) in enumerate(results, 1):
        command=record.get('command') or 'Unknown command'
        doc.add_heading(f'{idx}. {command}', level=2)
        if record.get('result') != 'completed':
            doc.add_paragraph(f"Capture status: {record.get('result', 'unknown')}")
        if include_text and record.get('text'):
            txtpath=(folder / str(record['text']).replace('\\','/')).resolve()
            if txtpath.is_relative_to(folder.resolve()) and txtpath.suffix.lower()=='.txt' and txtpath.is_file():
                content=txtpath.read_text(encoding='utf-8',errors='replace')[:100_000]
                para=doc.add_paragraph(style='Normal')
                para.paragraph_format.space_after=Pt(5)
                run=para.add_run(content or '[Empty command output]')
                run.font.name='Consolas';run.font.size=Pt(8)
        images=record.get('images') or ([record['image']] if record.get('image') else [])
        # Each continuation PNG belongs under the same command.
        if not images:
            doc.add_paragraph('[No screenshot recorded]')
        for name in images:
            try:
                path = safe_image_path(folder, name)
                if not path.is_file():
                    raise FileNotFoundError(name)
                with Image.open(path) as source:
                    img=source.convert('RGB')
                    # Image at 6.35in wide must fit on a Word page at the same scale.
                    max_slice_height=max(1, int(img.width * 8.0 / 6.35))
                    for top in range(0,img.height,max_slice_height):
                        part=img.crop((0,top,img.width,min(img.height,top+max_slice_height)))
                        stream=BytesIO()
                        part.save(stream,format='PNG')
                        stream.seek(0)
                        paragraph=doc.add_paragraph()
                        paragraph.alignment=WD_ALIGN_PARAGRAPH.CENTER
                        paragraph.paragraph_format.space_after=Pt(2)
                        paragraph.add_run().add_picture(stream,width=Inches(6.35))
            except (OSError, ValueError) as exc:
                doc.add_paragraph(f'[Screenshot unavailable: {name} — {exc}]')
    if not results:
        doc.add_paragraph('No command captures recorded.')


def export_word(run_folders, destination, combined=False, template=None, metadata_override=None):
    """Return list of produced DOCX paths. Separate mode generates one per run."""
    if template:
        return export_template(run_folders,destination,template,combined=combined,metadata_override=metadata_override)
    runs=[read_run(folder) for folder in run_folders]
    if not runs:
        raise ValueError('Select at least one capture run.')
    destination=Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    documents=[]
    if combined:
        groups=[runs]
    else:
        groups=[[run] for run in runs]
    used=set()
    for group in groups:
        doc=Document()
        section=doc.sections[0]
        section.top_margin=Inches(.65)
        section.bottom_margin=Inches(.65)
        normal=doc.styles['Normal']
        normal.font.name='Aptos'
        normal.font.size=Pt(9)
        title=doc.add_heading('Console Capture Evidence', 0)
        title.alignment=WD_ALIGN_PARAGRAPH.CENTER
        for index,(folder,data) in enumerate(group):
            add_run(doc,folder,data,index,combined)
        if combined:
            stem='Combined_Console_Report'
        else:
            folder,data=group[0]
            stem='{}_{}'.format(data.get('device') or 'Device',data.get('group') or 'Capture')
        import re
        stem=re.sub(r'[^A-Za-z0-9_.-]+','_',stem).strip('_.')[:90] or 'Report'
        count=1
        candidate=destination/(stem+'.docx')
        while candidate.exists() or candidate.name.lower() in used:
            count+=1
            candidate=destination/(f'{stem}_{count}.docx')
        doc.save(candidate)
        used.add(candidate.name.lower())
        documents.append(candidate)
    return documents

# Template export is deliberately independent of network access: it reads the
# existing run manifest and captured text/images, never probes a device.
import re

FIELD_NAMES = ('DATE', 'LABELNO', 'HOSTNAME', 'SERIALNO', 'MODELNO', 'DEVICENAME', 'COMPORT', 'CAPTUREDATE', 'COMMANDGROUP')


def _read_capture_text(folder, data, limit=3_000_000):
    parts=[]
    for result in data.get('results', []):
        relative=result.get('text')
        if not relative or not isinstance(relative,str):
            continue
        target=(folder/relative.replace('\\','/')).resolve()
        if not target.is_relative_to(folder.resolve()) or target.suffix.lower()!='.txt':
            continue
        try:
            with target.open('r',encoding='utf-8',errors='replace') as stream:
                parts.append(stream.read(min(300_000,max(0,limit-sum(map(len,parts))))))
        except OSError:
            pass
        if sum(map(len,parts))>=limit:break
    return '\n'.join(parts)


def extract_inventory(folder, data):
    """Conservative model/serial extraction; unknown values are never invented."""
    output=_read_capture_text(folder,data)
    def first(patterns):
        for expression in patterns:
            match=re.search(expression,output,re.I|re.M)
            if match:
                value=match.group(1).strip(' \t:;,')
                if value and len(value)<=100 and value.lower() not in {'unknown','n/a','none','-'}:
                    return value
        return 'Not detected'
    serial=first([
        r'^\s*(?:ESN|Electronic Serial Number|Serial\s*(?:No\.?|Number)|Device\s*SN|Chassis\s*SN)\s*[:=]\s*([A-Za-z0-9_.-]{5,80})\s*$',
        r'^\s*SN\s*[:=]\s*([A-Za-z0-9_.-]{5,80})\s*$',
        r'^\s*ESN\s+of\s+(?:slot|device|chassis)\s+[^:]*:\s*([A-Za-z0-9_.-]{5,80})\s*$'
    ])
    model=first([
        # Huawei VRP 'display version' identifies the platform in its uptime line.
        # Example: 'HUAWEI CloudEngine S5755-H uptime is ...'.
        r'^\s*(HUAWEI\s+CloudEngine\s+[A-Za-z0-9][A-Za-z0-9_.\/-]*)\s+uptime\s+is\b',
        r'^\s*(HUAWEI\s+[A-Za-z0-9][A-Za-z0-9_.\/-]*(?:\s+[A-Za-z0-9][A-Za-z0-9_.\/-]*){0,2})\s+uptime\s+is\b',
        r'^\s*(?:Product\s+Model|Device\s+Model|Model\s*(?:Number|No\.?)?|Device\s+Type)\s*[:=]\s*([A-Za-z0-9][A-Za-z0-9_. /-]{1,79})\s*$',
        r'^\s*(?:Product\s+Name|Board\s+Type)\s*[:=]\s*([A-Za-z0-9][A-Za-z0-9_. /-]{1,79})\s*$'
    ])
    hostname=str(data.get('cli_hostname') or '').strip()
    # Manifest's 'device' may just be a COM label, not a hostname.
    raw_date=str(data.get('started_at') or '')
    try: capture_date=datetime.fromisoformat(raw_date.replace('Z','+00:00')).strftime('%d-%m-%y (%H:%M)')
    except ValueError: capture_date=raw_date or 'Not recorded'
    return {'HOSTNAME':hostname or 'Not detected','DEVICENAME':hostname or 'Not detected',
            'DATE':capture_date,'LABELNO':'Not provided','SERIALNO':serial,'MODELNO':model,
            'COMPORT':str(data.get('com_port') or 'Not recorded'),
            'CAPTUREDATE':capture_date,
            'COMMANDGROUP':str(data.get('group') or 'Not recorded')}


def _replace_fields(paragraph, values):
    original=paragraph.text
    modified=original
    # Support both explicit double-brace placeholders and exact placeholder words.
    for key,value in values.items():
        modified=re.sub(r'\{\{\s*'+re.escape(key)+r'\s*\}\}',lambda _m:str(value),modified)
        modified=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(key)+r'(?![A-Za-z0-9_])',lambda _m:str(value),modified)
    if modified!=original:
        # A token may span several Word runs. Preserve paragraph/style and
        # first run's formatting; other formatting inside token is not retained.
        if paragraph.runs:
            paragraph.runs[0].text=modified
            for run in paragraph.runs[1:]:run.text=''
        else:
            paragraph.add_run(modified)


def _walk_paragraphs(container):
    for paragraph in container.paragraphs:
        yield paragraph
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from _walk_paragraphs(cell)


# Labels in a custom Word report map to capture commands, not to a fixed
# screenshot order. Short Huawei abbreviations are accepted in saved runs.
COMMAND_MARKERS = {
    'DISPLAYCLOCK': 'display clock',
    'DISPLAYVERSION': 'display version',
    'DISPLAYESN': 'display device esn',
    'DISPLAYCPU': 'display cpu-usage',
    'DISPLAYMEM': 'display memory all',
    'DISPLAYPOWER': 'display device power system',
    'DISPLAYTEMP': 'display device temperature',
    'DISPLAYFAN': 'display device fan',
    'DISPLAYALARM': 'display alarm active',
}


def _normalized_command(command):
    command=re.sub(r'\s+', ' ', str(command or '').strip().lower())
    # A filter does not change the underlying diagnostic command.
    command=command.split('|',1)[0].strip()
    words=command.split(' ')
    if words and words[0]=='dis': words[0]='display'
    return ' '.join(words)


def _record_for_marker(data, marker):
    expected=COMMAND_MARKERS[marker]
    matches=[entry for entry in data.get('results',[]) if _normalized_command(entry.get('command'))==expected]
    if not matches:
        return None
    # When a command was captured more than once, prefer the last completed one.
    return next((entry for entry in reversed(matches) if entry.get('result')=='completed'),matches[-1])


def _insert_images_into_marker_cell(cell, paragraph, folder, data, marker):
    record=_record_for_marker(data,marker)
    # Clear only the placeholder paragraph, not its table cell or row formatting.
    for run in paragraph.runs:run.text=''
    if not record:
        paragraph.add_run('[No capture for '+COMMAND_MARKERS[marker]+']')
        return
    images=record.get('images') or ([record['image']] if record.get('image') else [])
    if not images:
        paragraph.add_run('[No screenshot for '+COMMAND_MARKERS[marker]+']')
        return
    for name in images:
        try:
            path=safe_image_path(folder,name)
            if not path.is_file():raise FileNotFoundError(name)
            with Image.open(path) as source:
                img=source.convert('RGB')
                # Use the full *usable* table-cell width, instead of a fixed
                # 6.15-inch centered screenshot. Word's default cell margins
                # are typically 0.08 inches per side, so reserve 0.16 inches
                # plus a small safety margin to avoid table overflow.
                cell_width = cell.width.inches if cell.width else 6.99
                width_inches = max(0.5, cell_width - 0.20)
                max_height_px=max(1,int(img.width * 4.9 / width_inches))
                for top in range(0,img.height,max_height_px):
                    part=img.crop((0,top,img.width,min(img.height,top+max_height_px)))
                    stream=BytesIO();part.save(stream,format='PNG');stream.seek(0)
                    target=paragraph if top==0 and name==images[0] else cell.add_paragraph()
                    target.alignment=WD_ALIGN_PARAGRAPH.LEFT
                    target.paragraph_format.left_indent=Pt(0)
                    target.paragraph_format.right_indent=Pt(0)
                    target.paragraph_format.space_after=Pt(2)
                    target.add_run().add_picture(stream,width=Inches(width_inches))
        except (OSError,ValueError) as exc:
            cell.add_paragraph('[Screenshot unavailable: '+str(name)+' — '+str(exc)+']')


def _replace_image_markers(doc, folder, data):
    found=set()
    # Respect the original table layout, cell borders, headings, header/footer.
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in list(cell.paragraphs):
                    token=paragraph.text.strip()
                    token=token[2:-2].strip() if token.startswith('{{') and token.endswith('}}') else token
                    if token in COMMAND_MARKERS:
                        found.add(token)
                        _insert_images_into_marker_cell(cell,paragraph,folder,data,token)
    return found


def _fill_device_template(doc, folder, data, values):
    """Populate one complete copy of a user Word template for one device."""
    found_image_markers=_replace_image_markers(doc,folder,data)
    markers=[]
    for paragraph in list(_walk_paragraphs(doc)):
        if re.search(r'\{\{\s*CAPTURE_OUTPUTS\s*\}\}|\bCAPTURE_OUTPUTS\b',paragraph.text):
            markers.append(paragraph)
        else:
            _replace_fields(paragraph,values)
    for section in doc.sections:
        for part in (section.header,section.footer):
            for paragraph in _walk_paragraphs(part):_replace_fields(paragraph,values)
    if not markers and not found_image_markers:
        raise ValueError('Template needs CAPTURE_OUTPUTS or a recognized command image marker (e.g. DISPLAYVERSION).')
    if len(markers)>1:
        raise ValueError('Template must have exactly one CAPTURE_OUTPUTS marker.')
    if markers:
        marker=markers[0]
        if marker._p.getparent() is not doc.element.body:
            raise ValueError('CAPTURE_OUTPUTS must be a body paragraph, not inside a table.')
        if marker.text.strip() not in ('CAPTURE_OUTPUTS','{{CAPTURE_OUTPUTS}}'):
            raise ValueError('Put CAPTURE_OUTPUTS on its own paragraph.')
        insertion_start=len(doc.element.body)-1
        add_run(doc,folder,data,0,False,include_text=True)
        created=list(doc.element.body)[insertion_start:-1]
        anchor=marker._p
        for element in created:
            anchor.addnext(element)
            anchor=element
        marker._element.getparent().remove(marker._element)
    return doc


def _append_device_document(master, other):
    """Append a rendered device's tables and images with image relationships fixed.

    Both documents derive from exactly the same template, so their styles,
    headers and page setup agree. Avoid an extra dependency on docxcompose.
    """
    master.add_page_break()
    body=master.element.body
    last_section=body.sectPr
    for original in other.element.body:
        if original.tag==qn('w:sectPr'):
            continue
        element=deepcopy(original)
        # Embedded images use per-document relationship identifiers. Transfer
        # the binary image part and point copied XML at the new relationship.
        for node in element.iter():
            for attribute in (qn('r:embed'),qn('r:id'),qn('r:link')):
                old_rid=node.get(attribute)
                if not old_rid or old_rid not in other.part.rels:continue
                rel=other.part.rels[old_rid]
                if rel.reltype==RT.IMAGE:
                    new_rid,_image=master.part.get_or_add_image(BytesIO(rel.target_part.blob))
                elif rel.is_external:
                    new_rid=master.part.relate_to(rel.target_ref,rel.reltype,is_external=True)
                else:
                    raise ValueError('Combined template contains an unsupported linked object: '+rel.reltype)
                node.set(attribute,new_rid)
        last_section.addprevious(element)


def _append_evidence_tables(master, other):
    """Append only evidence tables for an additional device, never the cover."""
    if len(other.tables)<2:
        raise ValueError('Combined template must contain an inventory table and evidence tables.')
    master.add_page_break()
    last_section=master.element.body.sectPr
    for table_index,source_table in enumerate(other.tables[1:]):
        if table_index:
            master.add_page_break()  # Match the original template: each evidence table starts on a page.
        element=deepcopy(source_table._tbl)
        for node in element.iter():
            for attribute in (qn('r:embed'), qn('r:id'), qn('r:link')):
                old_rid=node.get(attribute)
                if not old_rid or old_rid not in other.part.rels:
                    continue
                rel=other.part.rels[old_rid]
                if rel.reltype==RT.IMAGE:
                    new_rid,_image=master.part.get_or_add_image(BytesIO(rel.target_part.blob))
                elif rel.is_external:
                    new_rid=master.part.relate_to(rel.target_ref,rel.reltype,is_external=True)
                else:
                    raise ValueError('Evidence table has an unsupported linked object: '+rel.reltype)
                node.set(attribute,new_rid)
        last_section.addprevious(element)


def _add_inventory_rows(master, template, extra_runs):
    """Copy the original unfilled inventory row to preserve fonts, borders, widths."""
    template_doc=Document(template)
    if not template_doc.tables or len(template_doc.tables[0].rows)<2:
        raise ValueError('Combined export requires an inventory table with a data row.')
    table=master.tables[0]
    sample_row=template_doc.tables[0].rows[1]._tr
    for row_number,(folder,data) in enumerate(extra_runs,start=2):
        row_xml=deepcopy(sample_row)
        table._tbl.append(row_xml)
        row=table.rows[-1]
        values=extract_inventory(folder,data)
        # Update only cells in the added row, not the already-populated report.
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                _replace_fields(paragraph,values)
        row.cells[0].text=str(row_number)


def export_template(run_folders, destination, template, combined=False, metadata_override=None):
    """Generate original-layout Word template for every run, or all in one file."""
    runs=[read_run(folder) for folder in run_folders]
    if not runs:raise ValueError('Select at least one capture run.')
    template=Path(template)
    if not template.is_file() or template.suffix.lower()!='.docx':
        raise ValueError('Select a valid .docx Word template.')
    metadata_override=metadata_override or {}
    if metadata_override and len(runs)!=1:
        raise ValueError('Manual fields can only be set when exporting one run.')
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    groups=[runs] if combined else [[run] for run in runs]
    results=[]
    for group in groups:
        folder,data=group[0]
        master=Document(template)
        values=extract_inventory(folder,data)
        values.update({k:str(v) for k,v in metadata_override.items() if k in FIELD_NAMES and v})
        _fill_device_template(master,folder,data,values)
        if combined and len(group)>1:
            _add_inventory_rows(master,template,group[1:])
            for next_folder,next_data in group[1:]:
                individual=Document(template)
                _fill_device_template(individual,next_folder,next_data,extract_inventory(next_folder,next_data))
                _append_evidence_tables(master,individual)
        base=('Combined_Console_Report' if combined else
              '{}_{}'.format(data.get('cli_hostname') or data.get('device') or 'Device',data.get('group') or 'Capture'))
        stem=re.sub(r'[^A-Za-z0-9_.-]+','_',base).strip('_.')[:80] or 'Report'
        candidate=destination/(stem+'.docx')
        i=2
        while candidate.exists():
            candidate=destination/(f'{stem}_{i}.docx');i+=1
        master.save(candidate)
        results.append(candidate)
    return results
