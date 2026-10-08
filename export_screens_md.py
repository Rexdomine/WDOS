import json

with open(r'C:\Users\atteh\OneDrive\Desktop\workspace\wdos\stage4_pdf_reference\stage4_screens_data.json', encoding='utf-8') as f:
    data = json.load(f)

with open(r'C:\Users\atteh\OneDrive\Desktop\workspace\wdos\stage4_pdf_reference\ALL_SCREENS_TEXT.md', 'w', encoding='utf-8') as out:
    for code, s in data.items():
        out.write(f'# {code} — {s["title"]}\n')
        out.write(f'Desktop Page: {s["desktop"]["pnum"]}, Mobile Page: {s["mobile"]["pnum"]}, State Page: {s["state"]["pnum"]}\n\n')
        out.write('## Desktop View Text:\n```\n')
        out.write(s['desktop']['text'])
        out.write('\n```\n\n')
        out.write('## Mobile View Text:\n```\n')
        out.write(s['mobile']['text'])
        out.write('\n```\n\n')
        out.write('## State & Interaction Contract Text:\n```\n')
        out.write(s['state']['text'])
        out.write('\n```\n\n---\n\n')

print('ALL_SCREENS_TEXT.md created successfully!')
