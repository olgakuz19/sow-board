import os
from pathlib import Path
os.chdir(Path(__file__).parent)

import streamlit as st
import requests
from datetime import datetime

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://ynvzpugktkcplkmhnxpj.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", st.secrets.get("supabase_key", ""))
BH_REST_URL  = st.secrets.get("BH_REST_URL", st.secrets.get("bh_rest_url", ""))
BH_TOKEN     = st.secrets.get("BH_TOKEN", st.secrets.get("bh_token", ""))

JO_IDS = list(range(13597, 13608))

SOW_MAP = {
    13597: ("Owen",   "Systems Analyst"),
    13598: ("Owen",   "Sr. Full Stack Engineer"),
    13599: ("Owen",   "Sr. Quality Engineer"),
    13600: ("Adam",   "Sr. Data Engineer"),
    13601: ("Adam",   "Sr. Systems Analyst"),
    13602: ("Adam",   "Sr. Full Stack Engineer"),
    13603: ("Adam",   "Sr. QA Engineer"),
    13604: ("Steven", "Sr. Full-Stack Engineer"),
    13605: ("Steven", "Backend Developer"),
    13606: ("Owen",   "Sr. Systems Analyst"),
    13607: ("Adam",   "SR. Quality Engineer"),
}

SOW_COLORS = {"Steven": "#7c3aed", "Adam": "#0369a1", "Owen": "#065f46"}

STATUS_COLOR = {
    "Client Submission": "#22c55e",
    "Submitted":         "#3b82f6",
    "AM Rejected":       "#6b7280",
}

FLAGS = ["", "Close to offer", "Coming off market", "Selected for hire", "Unreachable", "No longer available"]

# ── Supabase helpers ──────────────────────────────────────────────────────────

def _headers(prefer=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h

def get_all_candidates():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/sow_candidates?select=*&order=jo_number,id",
        headers=_headers()
    )
    return r.json() if r.status_code == 200 else []

def get_last_sync():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/sow_meta?key=eq.last_sync&select=value",
        headers=_headers()
    )
    try:
        data = r.json()
        if isinstance(data, list) and data:
            return data[0].get("value")
    except Exception:
        pass
    return None

def set_last_sync(ts):
    requests.post(
        f"{SUPABASE_URL}/rest/v1/sow_meta",
        headers=_headers("resolution=merge-duplicates"),
        json={"key": "last_sync", "value": ts}
    )

def save_availability(row_id, availability, flag):
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/sow_candidates?id=eq.{row_id}",
        headers=_headers(),
        json={"availability": availability, "flag": flag, "last_updated": datetime.utcnow().isoformat()}
    )

def delete_candidate(row_id):
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/sow_candidates?id=eq.{row_id}",
        headers=_headers()
    )

def upsert_candidate(jo_number, bh_sub_id, bh_cand_id, name, bh_status):
    requests.post(
        f"{SUPABASE_URL}/rest/v1/sow_candidates",
        headers=_headers("resolution=merge-duplicates"),
        json={"jo_number": jo_number, "bh_sub_id": bh_sub_id,
              "bh_cand_id": bh_cand_id, "name": name, "bh_status": bh_status}
    )

# ── BH sync ───────────────────────────────────────────────────────────────────

def sync_from_bh():
    if not BH_REST_URL or not BH_TOKEN:
        return False, "BH credentials not set in secrets"
    count = 0
    for jo_id in JO_IDS:
        r = requests.get(
            f"{BH_REST_URL}/entity/JobOrder/{jo_id}",
            params={"BhRestToken": BH_TOKEN, "fields": "id,submissions"},
            timeout=10
        )
        if r.status_code != 200:
            continue
        subs = r.json().get("data", {}).get("submissions", {}).get("data", [])
        for sub in subs:
            sid = sub["id"]
            r2 = requests.get(
                f"{BH_REST_URL}/entity/JobSubmission/{sid}",
                params={"BhRestToken": BH_TOKEN, "fields": "id,status,candidate"},
                timeout=10
            )
            if r2.status_code != 200:
                continue
            d = r2.json().get("data", {})
            cand = d.get("candidate", {})
            name = f"{cand.get('firstName','')} {cand.get('lastName','')}".strip().title()
            upsert_candidate(str(jo_id), sid, cand.get("id"), name, d.get("status", ""))
            count += 1
    set_last_sync(datetime.now().strftime("%Y-%m-%d %I:%M %p CST"))
    return True, f"Synced {count} submissions from BH"

# ── Page ──────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="SOW Interview Board · TPA Technologies", page_icon="📅", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] { display: none; }
.block-container { padding-top: 2rem; }
.sow-title { font-size: 26px; font-weight: 800; color: #f1f5f9; margin-bottom: 2px; }
.sow-sub   { color: #64748b; font-size: 13px; margin-bottom: 0; }
span.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────

col_title, col_btn = st.columns([4, 1])
with col_title:
    st.markdown('<div class="sow-title">📅 SOW Interview Availability Board</div>', unsafe_allow_html=True)
    last_sync = get_last_sync()
    st.markdown(f'<div class="sow-sub">Last BH sync: {last_sync or "Never"} &nbsp;·&nbsp; TPA Technologies</div>', unsafe_allow_html=True)

with col_btn:
    if st.button("🔄 Update from BH", use_container_width=True):
        with st.spinner("Syncing from Bullhorn..."):
            ok, msg = sync_from_bh()
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.warning(msg)

st.divider()

# ── Load data ─────────────────────────────────────────────────────────────────

all_cands = get_all_candidates()

if not all_cands:
    st.info("No candidates loaded yet.")
    st.stop()

# ── Summary ───────────────────────────────────────────────────────────────────

total    = len(all_cands)
has_avail = sum(1 for c in all_cands if c.get("availability","").strip())
missing  = total - has_avail

c1, c2, c3 = st.columns(3)
c1.metric("Total Candidates", total)
c2.metric("🟢 Have Availability", has_avail)
c3.metric("🔴 Missing Availability", missing)

st.divider()

# ── Group by SOW ──────────────────────────────────────────────────────────────

board = {}
for c in all_cands:
    jo = c["jo_number"]
    board.setdefault(jo, []).append(c)

sow_groups = {"Steven": [], "Adam": [], "Owen": []}
for jo_str, cands in board.items():
    sow, role = SOW_MAP.get(int(jo_str), ("Other", jo_str))
    sow_groups.setdefault(sow, []).append((jo_str, role, cands))

for sow_name, jos in sow_groups.items():
    if not jos:
        continue
    color = SOW_COLORS.get(sow_name, "#374151")
    st.markdown(f"""
    <div style="border-left:4px solid {color};padding-left:12px;margin:20px 0 10px 0">
      <span style="font-size:20px;font-weight:800;color:{color}">{sow_name} SOW</span>
    </div>
    """, unsafe_allow_html=True)

    for jo_str, role, cands in sorted(jos, key=lambda x: x[0]):
        has_jo  = sum(1 for c in cands if c.get("availability","").strip())
        total_jo = len(cands)
        label   = f"**{jo_str} · {role}** — {has_jo}/{total_jo} have availability"

        with st.expander(label, expanded=True):
            for cand in cands:
                row_id   = cand["id"]
                avail    = cand.get("availability", "") or ""
                flag     = cand.get("flag", "") or ""
                status   = cand.get("bh_status", "")
                icon     = "🟢" if avail.strip() else "🔴"
                s_color  = STATUS_COLOR.get(status, "#6b7280")

                c_icon, c_name, c_status, c_avail, c_flag, c_edit, c_del = st.columns([0.4, 2, 1.8, 3.5, 1.8, 0.6, 0.4])

                with c_icon:
                    st.markdown(f"<div style='padding-top:6px'>{icon}</div>", unsafe_allow_html=True)
                with c_name:
                    st.markdown(f"<div style='padding-top:6px;font-weight:600'>{cand['name']}</div>", unsafe_allow_html=True)
                with c_status:
                    st.markdown(f"<div style='padding-top:6px'><span class='badge' style='background:{s_color}'>{status}</span></div>", unsafe_allow_html=True)
                with c_avail:
                    display = avail if avail.strip() else "<span style='color:#475569;font-style:italic'>No availability provided</span>"
                    st.markdown(f"<div style='padding-top:6px;font-size:13px'>{display}</div>", unsafe_allow_html=True)
                with c_flag:
                    if flag:
                        st.markdown(f"<div style='padding-top:6px;color:#f59e0b;font-size:12px'>⚠️ {flag}</div>", unsafe_allow_html=True)
                with c_edit:
                    if st.button("✏️", key=f"e_{row_id}", help="Edit"):
                        st.session_state[f"editing_{row_id}"] = True
                with c_del:
                    if st.button("🗑️", key=f"d_{row_id}", help="Remove candidate"):
                        st.session_state[f"confirm_del_{row_id}"] = True

                # Delete confirmation
                if st.session_state.get(f"confirm_del_{row_id}"):
                    st.warning(f"Remove **{cand['name']}** from the board?")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button("Yes, remove", key=f"yes_{row_id}", type="primary"):
                            delete_candidate(row_id)
                            st.session_state.pop(f"confirm_del_{row_id}", None)
                            st.rerun()
                    with dc2:
                        if st.button("Cancel", key=f"no_{row_id}"):
                            st.session_state.pop(f"confirm_del_{row_id}", None)
                            st.rerun()

                # Edit form
                if st.session_state.get(f"editing_{row_id}"):
                    with st.form(key=f"form_{row_id}"):
                        new_avail = st.text_input("Availability", value=avail, placeholder="e.g. M-F 9am–5pm")
                        new_flag  = st.selectbox("Flag", FLAGS, index=FLAGS.index(flag) if flag in FLAGS else 0)
                        s1, s2 = st.columns(2)
                        with s1:
                            if st.form_submit_button("💾 Save", type="primary"):
                                save_availability(row_id, new_avail, new_flag)
                                st.session_state.pop(f"editing_{row_id}", None)
                                st.rerun()
                        with s2:
                            if st.form_submit_button("✖ Cancel"):
                                st.session_state.pop(f"editing_{row_id}", None)
                                st.rerun()
