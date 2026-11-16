"""Offline Word evidence export from Console Capture run summary files."""
import json
from pathlib import Path
from datetime import datetime
from docx import Document
from PIL import Image
from io import BytesIO
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


def add_run(doc, folder, data, index, combined):
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
        cells[1].text=str(data.get(key) or '—')
    results=sorted(enumerate(data['results']), key=lambda p: (p[1].get('order', p[0]+1),p[0]))
    for idx, (_, record) in enumerate(results, 1):
        command=record.get('command') or 'Unknown command'
        doc.add_heading(f'{idx}. {command}', level=2)
        if record.get('result') != 'completed':
            doc.add_paragraph(f"Capture status: {record.get('result', 'unknown')}")
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


def export_word(run_folders, destination, combined=False):
    """Return list of produced DOCX paths. Separate mode generates one per run."""
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
