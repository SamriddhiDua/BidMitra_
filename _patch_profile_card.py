"""Patch the profile card in app.py to show override values."""
import pathlib, re

APP = pathlib.Path("app.py")
content = APP.read_text(encoding="utf-8")

# Use regex to find and replace the profile card block regardless of minor spacing
pattern = re.compile(
    r'# ---- Profile card ----\n'
    r'    pct = prof\.completeness_pct\(\)\n'
    r'    pct_color = .+\n'
    r'\n'
    r'    st\.markdown\(f""".*?""", unsafe_allow_html=True\)',
    re.DOTALL
)

NEW = '''# ---- Profile card: shows active (possibly overridden) values ----
    pct = prof.completeness_pct()
    pct_color = "#16a34a" if pct >= 80 else "#d97706" if pct >= 50 else "#dc2626"

    active_radius = merged_overrides.get("delivery_radius_km", prof.delivery_radius_km)
    active_emd    = merged_overrides.get("max_emd_inr", prof.max_emd_inr)
    radius_ovr = " <span style='color:#f59e0b;font-size:0.72rem'>(override)</span>" \\
        if float(active_radius) != float(prof.delivery_radius_km) else ""
    emd_ovr = " <span style='color:#f59e0b;font-size:0.72rem'>(override)</span>" \\
        if float(active_emd) != float(prof.max_emd_inr) else ""

    st.markdown(f"""
<div class="profile-card">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
    <div>
      <h2 style="margin:0; font-size:1.4rem;">{prof.business_name or "Unnamed Business"}</h2>
      <span style="color:#6b7280; font-size:0.9rem;">\U0001f4cd {prof.base_location} &nbsp;\xb7&nbsp;
        Radius {float(active_radius):.0f} km{radius_ovr} &nbsp;\xb7&nbsp; Max EMD \u20b9{float(active_emd):,.0f}{emd_ovr}</span>
    </div>
    <div style="text-align:right;">
      <span style="font-size:1.1rem; font-weight:700; color:{pct_color};">{pct}%</span><br>
      <span style="font-size:0.75rem; color:#6b7280;">Profile completeness</span>
    </div>
  </div>
  <div class="completeness-bar-outer" style="margin:10px 0 4px;">
    <div class="completeness-bar-inner" style="width:{pct}%; background:{pct_color};"></div>
  </div>
</div>
""", unsafe_allow_html=True)'''

m = pattern.search(content)
if m:
    content = content[:m.start()] + NEW + content[m.end():]
    APP.write_text(content, encoding="utf-8")
    print("PATCHED OK")
else:
    print("PATTERN NOT MATCHED")
    # Show what's around the marker
    idx = content.find("# ---- Profile card")
    if idx >= 0:
        print(repr(content[idx:idx+300]))
