import re

input_path = r"C:\Users\lenovo\OneDrive\Desktop\bessai_presentacion_cen.html"
output_path = r"C:\Users\lenovo\OneDrive\Desktop\02_Proyectos_Tech\open-bess-edge\bessai_presentacion_fusion.html"

with open(input_path, "r", encoding="utf-8") as f:
    html = f.read()

old_root = """:root {
  --cen-navy: #1a2b4a;
  --cen-blue: #003087;
  --cen-accent: #0072ce;
  --cen-light: #e8f1fb;
  --cen-gold: #f5a623;
  --cen-green: #2d8a4e;
  --cen-gray: #5a6472;
  --cen-light-gray: #f4f6f9;
  --cen-border: #d0dae8;
  --cen-white: #ffffff;
  --slide-w: 100%;
}"""

new_root = """:root {
  --cen-navy: #f3f4f6;       /* Primary Text (Light) */
  --cen-blue: #0a0f18;       /* bgdark for Headers/Accents */
  --cen-accent: #f59e0b;     /* Orange Accent */
  --cen-light: #1f2937;      /* Muted backgrounds inside cards */
  --cen-gold: #f59e0b;       /* Orange Accent */
  --cen-green: #22c55e;      /* Success Green */
  --cen-gray: #cecdcd;       /* Secondary Text / Muted */
  --cen-light-gray: #0a0f18; /* Body Background */
  --cen-border: #374151;     /* Subtle borders */
  --cen-white: #111827;      /* Slide Card Background (bgcard) */
  --slide-w: 100%;
}"""

html = html.replace(old_root, new_root)
html = re.sub(r'background: linear-gradient\(135deg, #f8fafd 0%, #edf2fb 100%\);', r'background: linear-gradient(135deg, #111827 0%, #0a0f18 100%);', html)
html = re.sub(r'color:\s*var\(--cen-blue\);\s*\n\s*line-height:\s*1.05;', r'color: var(--cen-navy);\n  line-height: 1.05;', html)
html = re.sub(r'\.slide-title \{\s*\n\s*font-family(.*?)\n\s*font-size(.*?)\n\s*font-weight(.*?)\n\s*color:\s*#ffffff;', 
              r'.slide-title {\n  font-family\1\n  font-size\2\n  font-weight\3\n  color: var(--cen-accent);', html)
html = re.sub(r'background:\s*#f0f6ff;', r'background: #1f2937;', html)
html = re.sub(r'background:\s*#fffbf2;', r'background: #1f2937;', html)
html = re.sub(r'background:\s*#f0faf4;', r'background: #1f2937;', html)
html = re.sub(r'background:\s*#e8f1fb\s*!important;', r'background: #1f2937 !important;', html)
html = re.sub(r'color:\s*var\(--cen-blue\)\s*!important;', r'color: #f3f4f6 !important;', html)
html = re.sub(r'\.tag-green \{ background: #d1f5e0; color: #155d30; \}', r'.tag-green { background: rgba(34,197,94,0.15); color: #22c55e; }', html)
html = re.sub(r'\.tag-blue \{ background: var\(--cen-light\); color: var\(--cen-blue\); \}', r'.tag-blue { background: rgba(245,158,11,0.15); color: #f59e0b; }', html)
html = re.sub(r'\.tag-gold \{ background: #fff0c4; color: #7a5100; \}', r'.tag-gold { background: rgba(245,158,11,0.15); color: #f59e0b; }', html)
html = html.replace('stroke="#003087"', 'stroke="#374151"')
html = re.sub(r'\.kpi-value \{\n\s*font-family(.*?)\n\s*font-size(.*?)\n\s*font-weight(.*?)\n\s*color:\s*var\(--cen-blue\);',
              r'.kpi-value {\n  font-family\1\n  font-size\2\n  font-weight\3\n  color: var(--cen-accent);', html)
html = re.sub(r'\.arch-node\.blue \{\s*\n\s*background:\s*var\(--cen-blue\);\s*\n\s*color:\s*#fff;',
              r'.arch-node.blue {\n  background: var(--cen-light);\n  color: var(--cen-accent);', html)
html = re.sub(r'\.arch-node\.gold \{\s*\n\s*background:\s*var\(--cen-gold\);\s*\n\s*color:\s*#5a3a00;',
              r'.arch-node.gold {\n  background: rgba(245,158,11,0.15);\n  color: var(--cen-accent);', html)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Done generating fusion HTML.")
