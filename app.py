"""
app.py  -  SentientOS Premium Futuristic Dashboard
Run: streamlit run app.py
"""
import html
import uuid
from datetime import datetime

import streamlit as st

st.set_page_config(
    page_title="SentientOS",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

from sentientos import database as db
from sentientos.executor import execute_plan, get_system_metrics, HELP_TEXT
from sentientos.planner import parse_command, DEMO_COMMANDS
from sentientos.security import describe_policy
from sentientos.tools import get_workspace_summary
# =============================================================================
# DESIGN SYSTEM CSS  (all hex — no CSS vars to avoid Streamlit resolution bugs)
# =============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* CSS VARIABLES & ROOT — BORDO (#6C151E) · GREEN (#0F3D3A) · CREAM (#F5DABF) */
:root, html, body, .stApp, [data-testid="stAppViewContainer"] {
  --bordo: #6C151E;
  --bordo-light: #8E1F2A;
  --bordo-glow: rgba(108, 21, 30, 0.45);
  --green: #0F3D3A;
  --green-deep: #071A18;
  --green-surface: #0B2725;
  --green-light: #185E5A;
  --cream: #F5DABF;
  --cream-dim: #D9BF9F;
  --cream-muted: rgba(245, 218, 191, 0.65);
  --cream-border: rgba(245, 218, 191, 0.15);
  --ok: #3DD598;
  --warn: #F5DABF;
  --err: #FF6B7A;
}

/* BASE */
html, body { background: #071A18 !important; color: #F5DABF !important; }
[class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: #071A18 !important; min-height: 100vh; }
header[data-testid="stHeader"], footer, #MainMenu { display: none !important; }

/* BACKGROUND GRID & AMBIENT DEPTH */
.stApp::before {
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(rgba(245, 218, 191, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(245, 218, 191, 0.025) 1px, transparent 1px);
  background-size: 60px 60px;
}
.stApp::after {
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(ellipse 80% 50% at 20% 0%, rgba(108, 21, 30, 0.14) 0%, transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 100%, rgba(15, 61, 58, 0.35) 0%, transparent 60%);
}

/* SIDEBAR */
[data-testid="stSidebar"] {
  background: #0B2725 !important;
  border-right: 1px solid rgba(245, 218, 191, 0.12) !important;
  padding: 0 !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
[data-testid="stSidebar"] * { color: #F5DABF; }

/* NAV BRAND */
.nav-brand {
  padding: 24px 18px 18px;
  border-bottom: 1px solid rgba(245, 218, 191, 0.12);
  margin-bottom: 6px; position: relative; overflow: hidden;
}
.nav-brand::before {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(108, 21, 30, 0.15) 0%, rgba(15, 61, 58, 0.2) 100%);
}
.nav-logo {
  font-size: 1.25rem; font-weight: 800; letter-spacing: -0.02em;
  color: #F5DABF; position: relative;
}
.nav-logo-blue   { color: #F5DABF; }
.nav-logo-violet { color: #8E1F2A; text-shadow: 0 0 12px rgba(108, 21, 30, 0.5); }
.nav-tagline { font-size: 0.63rem; color: rgba(245, 218, 191, 0.65); letter-spacing: 0.12em; text-transform: uppercase; margin-top: 4px; position: relative; }
.nav-version {
  display: inline-flex; align-items: center; gap: 4px;
  background: rgba(108, 21, 30, 0.25); border: 1px solid rgba(108, 21, 30, 0.5);
  border-radius: 20px; padding: 2px 8px; font-size: 0.6rem;
  color: #F5DABF; margin-top: 6px; position: relative;
}
.nav-section-label {
  font-size: 0.6rem; font-weight: 700; color: rgba(245, 218, 191, 0.45);
  text-transform: uppercase; letter-spacing: 0.15em; padding: 14px 18px 5px;
}

/* BUTTONS — FORCE CRISP, HIGH-CONTRAST, 100% VISIBLE TEXT */
.stButton button,
.stButton button *,
.stButton button p,
.stButton button span,
.stButton button div {
  font-family: 'Inter', sans-serif !important;
  font-size: 0.88rem !important;
  font-weight: 600 !important;
  color: #F5DABF !important;
  -webkit-text-fill-color: #F5DABF !important;
  opacity: 1 !important;
  visibility: visible !important;
}

.stButton > button {
  border-radius: 8px !important;
  font-weight: 600 !important;
  transition: all 0.18s ease !important;
  border: 1px solid rgba(245, 218, 191, 0.18) !important;
  background: rgba(15, 61, 58, 0.45) !important;
  color: #F5DABF !important;
  -webkit-text-fill-color: #F5DABF !important;
  padding: 10px 16px !important;
  width: 100% !important;
}
.stButton > button:hover {
  background: rgba(108, 21, 30, 0.38) !important;
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
  border-color: rgba(245, 218, 191, 0.45) !important;
  box-shadow: 0 0 16px rgba(108, 21, 30, 0.4) !important;
  transform: translateY(-1px) !important;
}
.stButton > button:active { transform: scale(0.98) !important; }

/* FORM SUBMIT BUTTONS (Execute Goal, Clear, Help) */
[data-testid="stFormSubmitButton"] button,
[data-testid="stFormSubmitButton"] button *,
[data-testid="stFormSubmitButton"] button p,
[data-testid="stFormSubmitButton"] button span,
[data-testid="stFormSubmitButton"] button div {
  font-family: 'Inter', sans-serif !important;
  font-weight: 700 !important;
  opacity: 1 !important;
  visibility: visible !important;
}

/* Primary Hero Button: Execute Goal (First column in form) */
[data-testid="column"]:first-child [data-testid="stFormSubmitButton"] button,
[data-testid="stFormSubmitButton"] button {
  background: linear-gradient(135deg, #8E1F2A 0%, #6C151E 100%) !important;
  color: #F5DABF !important;
  -webkit-text-fill-color: #F5DABF !important;
  border: 1px solid rgba(245, 218, 191, 0.4) !important;
  font-weight: 700 !important;
  font-size: 0.95rem !important;
  border-radius: 10px !important;
  padding: 12px 24px !important;
  box-shadow: 0 4px 24px rgba(108, 21, 30, 0.6) !important;
  letter-spacing: 0.02em !important;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8) !important;
}
[data-testid="column"]:first-child [data-testid="stFormSubmitButton"] button *,
[data-testid="column"]:first-child [data-testid="stFormSubmitButton"] button p,
[data-testid="stFormSubmitButton"] button *,
[data-testid="stFormSubmitButton"] button p {
  color: #F5DABF !important;
  -webkit-text-fill-color: #F5DABF !important;
  font-weight: 700 !important;
  font-size: 0.95rem !important;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8) !important;
  opacity: 1 !important;
}
[data-testid="column"]:first-child [data-testid="stFormSubmitButton"] button:hover,
[data-testid="stFormSubmitButton"] button:hover {
  background: linear-gradient(135deg, #A52535 0%, #7E1923 100%) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 8px 36px rgba(108, 21, 30, 0.8) !important;
  border-color: #F5DABF !important;
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}

/* Secondary Action Buttons in Form: Clear & Help (Columns 2 and 3) */
[data-testid="column"]:nth-child(2) [data-testid="stFormSubmitButton"] button,
[data-testid="column"]:nth-child(3) [data-testid="stFormSubmitButton"] button {
  background: rgba(15, 61, 58, 0.85) !important;
  border: 1px solid rgba(245, 218, 191, 0.28) !important;
  color: #F5DABF !important;
  -webkit-text-fill-color: #F5DABF !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  border-radius: 10px !important;
  padding: 12px 18px !important;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3) !important;
  text-shadow: none !important;
}
[data-testid="column"]:nth-child(2) [data-testid="stFormSubmitButton"] button *,
[data-testid="column"]:nth-child(2) [data-testid="stFormSubmitButton"] button p,
[data-testid="column"]:nth-child(3) [data-testid="stFormSubmitButton"] button *,
[data-testid="column"]:nth-child(3) [data-testid="stFormSubmitButton"] button p {
  color: #F5DABF !important;
  -webkit-text-fill-color: #F5DABF !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  text-shadow: none !important;
  opacity: 1 !important;
}
[data-testid="column"]:nth-child(2) [data-testid="stFormSubmitButton"] button:hover,
[data-testid="column"]:nth-child(3) [data-testid="stFormSubmitButton"] button:hover {
  background: rgba(24, 94, 90, 0.95) !important;
  border-color: #F5DABF !important;
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
  box-shadow: 0 0 16px rgba(245, 218, 191, 0.25) !important;
}

/* STATUS BAR */
.status-bar {
  background: rgba(11, 39, 37, 0.96); border-bottom: 1px solid rgba(245, 218, 191, 0.12);
  padding: 8px 24px; display: flex; align-items: center; gap: 18px;
  font-size: 0.75rem; flex-wrap: wrap; backdrop-filter: blur(10px);
  position: relative; z-index: 10; margin-bottom: 28px;
}
.status-pill {
  display: flex; align-items: center; gap: 5px; padding: 3px 10px;
  border-radius: 20px; background: rgba(15, 61, 58, 0.5);
  border: 1px solid rgba(245, 218, 191, 0.14);
}
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.dot-ok   { background: #3DD598; box-shadow: 0 0 6px rgba(61, 213, 152, 0.6); }
.dot-warn { background: #F5DABF; box-shadow: 0 0 6px rgba(245, 218, 191, 0.5); }
.dot-blue { background: #8E1F2A; box-shadow: 0 0 6px rgba(142, 31, 42, 0.6); }
.dot-err  { background: #FF6B7A; box-shadow: 0 0 6px rgba(255, 107, 122, 0.6); }
.status-label { color: rgba(245, 218, 191, 0.65); font-size: 0.72rem; }
.status-val   { color: #F5DABF; font-weight: 500; }
.status-div   { color: rgba(245, 218, 191, 0.2); }

@keyframes pulse-dot { 0%,100%{opacity:1;} 50%{opacity:0.5;} }
.dot-ok { animation: pulse-dot 2.5s ease-in-out infinite; }

/* PAGE HEADERS */
.page-header { margin-bottom: 24px; position: relative; z-index: 1; }
.page-title  { font-size: 1.7rem; font-weight: 800; letter-spacing: -0.03em; color: #FFF5EB; margin: 0; }
.page-subtitle { font-size: 0.845rem; color: rgba(245, 218, 191, 0.75); margin-top: 5px; }

/* GLASS CARDS */
.glass-card {
  background: rgba(15, 61, 58, 0.55);
  border: 1px solid rgba(245, 218, 191, 0.14);
  border-radius: 14px; padding: 22px 20px;
  backdrop-filter: blur(16px);
  position: relative; overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.glass-card:hover { border-color: rgba(245, 218, 191, 0.3); box-shadow: 0 8px 40px rgba(7, 26, 24, 0.45); }
.card-title   { font-size: 0.68rem; font-weight: 700; color: #F5DABF; text-transform: uppercase; letter-spacing: 0.12em; margin: 0 0 14px; }
.card-title-v { color: #8E1F2A; }
.card-title-c { color: #3DD598; }

/* METRIC CARDS */
.metric-card {
  background: rgba(15, 61, 58, 0.5);
  border: 1px solid rgba(245, 218, 191, 0.14);
  border-radius: 12px; padding: 18px 16px; text-align: center;
  transition: transform 0.2s, border-color 0.2s;
}
.metric-card:hover { transform: translateY(-2px); border-color: rgba(245, 218, 191, 0.3); }
.metric-val   { font-size: 1.8rem; font-weight: 800; color: #F5DABF; line-height: 1.1; }
.metric-label { font-size: 0.67rem; color: rgba(245, 218, 191, 0.65); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.1em; }

/* BADGES */
.badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 9px; border-radius: 20px; font-size: 0.68rem; font-weight: 600;
  letter-spacing: 0.04em; text-transform: uppercase;
}
.b-done   { background: rgba(61, 213, 152, 0.15); color: #3DD598; border: 1px solid rgba(61, 213, 152, 0.35); }
.b-failed { background: rgba(108, 21, 30, 0.3);  color: #FF6B7A; border: 1px solid rgba(184, 50, 64, 0.4); }
.b-pending{ background: rgba(245, 218, 191, 0.12); color: #F5DABF; border: 1px solid rgba(245, 218, 191, 0.3); }
.b-running{ background: rgba(108, 21, 30, 0.25); color: #F5DABF; border: 1px solid rgba(184, 50, 64, 0.4); }
.b-denied { background: rgba(108, 21, 30, 0.25); color: #FF8A96; border: 1px solid rgba(184, 50, 64, 0.35); }
.b-info   { background: rgba(15, 61, 58, 0.4);  color: #F5DABF; border: 1px solid rgba(245, 218, 191, 0.2); }
.b-warn2  { background: rgba(245, 218, 191, 0.1); color: #F5DABF; border: 1px solid rgba(245, 218, 191, 0.25); }
.b-skip   { background: rgba(245, 218, 191, 0.06); color: rgba(245, 218, 191, 0.5); border: 1px solid rgba(245, 218, 191, 0.1); }
.badge-dot { width: 5px; height: 5px; border-radius: 50%; }

/* STEP TIMELINE */
.step-row {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 10px 0; border-bottom: 1px solid rgba(245, 218, 191, 0.08);
}
.step-row:last-child { border-bottom: none; }
.step-num {
  width: 26px; height: 26px; border-radius: 50%; display: flex;
  align-items: center; justify-content: center; font-size: 0.72rem;
  font-weight: 700; flex-shrink: 0; font-family: 'JetBrains Mono', monospace;
}
.sn-pending  { background: rgba(245, 218, 191, 0.06); color: rgba(245, 218, 191, 0.4); border: 1px solid rgba(245, 218, 191, 0.12); }
.sn-done     { background: rgba(61, 213, 152, 0.15);  color: #3DD598; border: 1px solid rgba(61, 213, 152, 0.35); }
.sn-failed   { background: rgba(108, 21, 30, 0.3);   color: #FF6B7A; border: 1px solid rgba(184, 50, 64, 0.4); }
.sn-running  { background: rgba(108, 21, 30, 0.25);  color: #F5DABF; border: 1px solid rgba(184, 50, 64, 0.4); }
.sn-approval { background: rgba(245, 218, 191, 0.15); color: #F5DABF; border: 1px solid rgba(245, 218, 191, 0.35); }
.sn-skipped  { background: rgba(245, 218, 191, 0.04); color: rgba(245, 218, 191, 0.3); border: 1px dashed rgba(245, 218, 191, 0.1); }
.sn-denied   { background: rgba(108, 21, 30, 0.2);   color: #FF8A96; border: 1px solid rgba(184, 50, 64, 0.3); }
.step-body   { flex: 1; }
.step-hdr    { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.step-desc   { font-size: 0.845rem; color: #F5DABF; font-weight: 500; flex: 1; }
.step-tool   {
  font-family: 'JetBrains Mono', monospace; font-size: 0.63rem; color: rgba(245, 218, 191, 0.7);
  background: rgba(15, 61, 58, 0.4); padding: 1px 7px; border-radius: 4px;
  border: 1px solid rgba(245, 218, 191, 0.15);
}
.step-err {
  margin-top: 6px; padding: 6px 10px; background: rgba(108, 21, 30, 0.2);
  border: 1px solid rgba(184, 50, 64, 0.3);
  border-radius: 6px; font-size: 0.74rem; color: #FF6B7A;
}

/* INPUT */
[data-testid="stTextInput"] input {
  background: rgba(11, 39, 37, 0.95) !important;
  border: 1px solid rgba(245, 218, 191, 0.25) !important;
  border-radius: 10px !important; color: #F5DABF !important;
  -webkit-text-fill-color: #F5DABF !important;
  font-family: 'Inter', sans-serif !important; font-size: 0.92rem !important;
  padding: 11px 16px !important;
}
[data-testid="stTextInput"] input:focus {
  border-color: #8E1F2A !important;
  box-shadow: 0 0 0 3px rgba(108, 21, 30, 0.25), 0 0 20px rgba(108, 21, 30, 0.2) !important;
}
[data-testid="stTextInput"] input::placeholder { color: rgba(245, 218, 191, 0.45) !important; -webkit-text-fill-color: rgba(245, 218, 191, 0.45) !important; }
[data-testid="stTextInput"] label,
[data-testid="stTextInput"] label p { color: #F5DABF !important; -webkit-text-fill-color: #F5DABF !important; font-weight: 500 !important; }

/* TERMINAL */
.terminal {
  background: #051312; border: 1px solid rgba(245, 218, 191, 0.16);
  border-radius: 12px; padding: 16px 18px; font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem; color: #F5DABF; min-height: 120px;
  max-height: 340px; overflow-y: auto; line-height: 1.55;
  box-shadow: inset 0 2px 10px rgba(0,0,0,0.4);
}
.term-line  { margin: 3px 0; line-height: 1.55; color: #F5DABF; }
.term-ok    { color: #3DD598 !important; }
.term-err   { color: #FF6B7A !important; }
.term-warn  { color: #F5DABF !important; }
.term-info  { color: #8ED8D2 !important; }
.term-muted { color: rgba(245, 218, 191, 0.45) !important; }
.term-prompt{ color: #8E1F2A !important; }

/* POLICY ROWS */
.p-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0; border-bottom: 1px solid rgba(245, 218, 191, 0.08);
}
.p-row:last-child { border-bottom: none; }
.p-key  { font-size: 0.82rem; color: rgba(245, 218, 191, 0.7); }
.p-ok   { font-size: 0.8rem; color: #3DD598; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
.p-warn { font-size: 0.8rem; color: #FF6B7A; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
.p-info { font-size: 0.8rem; color: #F5DABF; font-weight: 500; font-family: 'JetBrains Mono', monospace; }
.p-cyan { font-size: 0.8rem; color: #8ED8D2; font-weight: 600; font-family: 'JetBrains Mono', monospace; }

/* LOGS */
.log-row {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 7px 0; border-bottom: 1px solid rgba(245, 218, 191, 0.06);
  font-size: 0.75rem;
}
.log-row:last-child { border-bottom: none; }
.log-ts     { color: rgba(245, 218, 191, 0.45); font-family: 'JetBrains Mono', monospace; font-size: 0.66rem; white-space: nowrap; padding-top: 1px; min-width: 68px; }
.log-icon   { font-size: 0.8rem; flex-shrink: 0; color: #F5DABF; }
.log-action { color: #F5DABF; flex: 1; word-break: break-word; line-height: 1.45; font-size: 0.78rem; }
.log-cat    { font-size: 0.58rem; color: rgba(245, 218, 191, 0.4); text-transform: uppercase; letter-spacing: 0.07em; padding-top: 2px; white-space: nowrap; }

/* EMPTY STATES */
.empty-st { text-align: center; padding: 36px 16px; }
.empty-st-icon  { font-size: 2rem; margin-bottom: 8px; opacity: 0.35; color: #F5DABF; }
.empty-st-title { font-size: 0.88rem; color: #F5DABF; margin-bottom: 4px; font-weight: 600; }
.empty-st-desc  { font-size: 0.76rem; color: rgba(245, 218, 191, 0.5); }

/* SECTION HEADER */
.sec-hdr   { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.sec-title { font-size: 0.68rem; font-weight: 700; color: #F5DABF; text-transform: uppercase; letter-spacing: 0.12em; }

/* APPROVAL CARD */
.approval-card {
  background: rgba(108, 21, 30, 0.25); border: 1px solid rgba(184, 50, 64, 0.45);
  border-radius: 12px; padding: 18px 20px; margin-top: 16px;
  position: relative; overflow: hidden;
}
.approval-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, #8E1F2A, transparent);
}
.approval-title { font-size: 0.9rem; font-weight: 700; color: #F5DABF; margin: 0 0 8px; }
.approval-detail {
  font-size: 0.76rem; color: #F5DABF; font-family: 'JetBrains Mono', monospace;
  background: rgba(5, 19, 18, 0.65); padding: 10px 12px; border-radius: 6px;
  margin-top: 10px; word-break: break-all; border: 1px solid rgba(245, 218, 191, 0.15);
}

/* ORB ANIMATIONS */
@keyframes orb-spin  { from{transform:rotate(0deg);} to{transform:rotate(360deg);} }
@keyframes orb-pulse { 0%,100%{opacity:0.8;transform:scale(1);} 50%{opacity:1;transform:scale(1.04);} }
@keyframes float-up  { from{opacity:0;transform:translateY(12px);} to{opacity:1;transform:translateY(0);} }

.orb-container { display:flex;align-items:center;justify-content:center;width:110px;height:110px;position:relative;flex-shrink:0; }
.orb {
  width:72px;height:72px;border-radius:50%;position:relative;
  background:radial-gradient(circle at 35% 35%, rgba(184, 50, 64, 0.95) 0%, rgba(108, 21, 30, 0.8) 35%, rgba(15, 61, 58, 0.85) 65%, rgba(245, 218, 191, 0.3) 90%, transparent 100%);
  box-shadow: 0 0 28px rgba(108, 21, 30, 0.55), 0 0 56px rgba(15, 61, 58, 0.4), inset 0 0 16px rgba(245, 218, 191, 0.15);
  animation: orb-pulse 4s ease-in-out infinite;
}
.orb-ring {
  position:absolute;inset:-12px;border-radius:50%;
  border:1.5px solid rgba(245, 218, 191, 0.35);
  animation:orb-spin 8s linear infinite;
}
.orb-ring2 { position:absolute;inset:-20px;border-radius:50%;border:1px dashed rgba(184, 50, 64, 0.35);animation:orb-spin 14s linear infinite reverse; }
.orb-glow  { position:absolute;inset:-30px;border-radius:50%;background:radial-gradient(circle,rgba(108, 21, 30, 0.2) 0%,rgba(15, 61, 58, 0.15) 50%,transparent 70%); }

/* COMMAND HERO */
.cmd-hero {
  background: rgba(15, 61, 58, 0.65); border:1px solid rgba(245, 218, 191, 0.2);
  border-radius:16px; padding:32px 28px 26px; margin-bottom:20px;
  backdrop-filter:blur(20px); position:relative; overflow:hidden;
  animation:float-up 0.35s ease-out;
}
.cmd-hero::before {
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,#6C151E,#F5DABF,#0F3D3A,transparent);opacity:0.6;
}
.cmd-title { font-size:1.9rem;font-weight:800;letter-spacing:-0.03em;color:#FFF5EB;margin:0 0 4px; }
.cmd-sub   { font-size:0.9rem;color:rgba(245, 218, 191, 0.75);margin-bottom:18px; }

/* PIPELINE */
.pipeline { display:flex;align-items:center;gap:0;padding:12px;overflow-x:auto; }
.pipe-stage { display:flex;flex-direction:column;align-items:center;gap:5px;min-width:76px;padding:8px 4px;border-radius:10px; }
.pipe-icon  { width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:0.88rem; }
.pipe-label { font-size:0.55rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em; }
.pipe-conn  { flex:1;height:1px;min-width:8px;max-width:28px;background:rgba(245, 218, 191, 0.15);margin-bottom:20px; }

.ps-done    .pipe-icon  { background:rgba(61, 213, 152, 0.15);color:#3DD598;border:1px solid rgba(61, 213, 152, 0.4); }
.ps-done    .pipe-label { color:#3DD598; }
.ps-running .pipe-icon  { background:rgba(108, 21, 30, 0.35);color:#F5DABF;border:1.5px solid #8E1F2A;box-shadow:0 0 14px rgba(142, 31, 42, 0.5); }
.ps-running .pipe-label { color:#F5DABF; font-weight:700; }
.ps-pending .pipe-icon  { background:rgba(245, 218, 191, 0.05);color:rgba(245, 218, 191, 0.35);border:1px solid rgba(245, 218, 191, 0.1); }
.ps-pending .pipe-label { color:rgba(245, 218, 191, 0.35); }
.ps-failed  .pipe-icon  { background:rgba(108, 21, 30, 0.25);color:#FF6B7A;border:1px solid rgba(255, 107, 122, 0.4); }
.ps-failed  .pipe-label { color:#FF6B7A; }

/* EXPANDERS */
[data-testid="stExpander"] { background:rgba(11, 39, 37, 0.8) !important; border:1px solid rgba(245, 218, 191, 0.18) !important; border-radius:10px !important; }

/* CHIPS */
.chip {
  display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;
  background:rgba(15, 61, 58, 0.5);border:1px solid rgba(245, 218, 191, 0.18);
  font-size:0.72rem;color:#F5DABF;
}

/* SIDEBAR FOOTER */
.sidebar-footer { padding:14px 16px;border-top:1px solid rgba(245, 218, 191, 0.12);font-size:0.72rem;color:rgba(245, 218, 191, 0.65);line-height:1.9; }
.sidebar-footer code { font-size:0.65rem !important;color:#F5DABF !important;background:rgba(5, 19, 18, 0.8) !important;border:1px solid rgba(245, 218, 191, 0.15) !important;padding:1px 5px !important;border-radius:4px !important; }
.online-dot { display:inline-block;width:6px;height:6px;border-radius:50%;background:#3DD598;margin-right:5px;vertical-align:middle;animation:pulse-dot 2.5s ease-in-out infinite; }

/* FEATURE CARDS — BORDO (#6C151E) · GREEN (#0F3D3A) · CREAM (#F5DABF) */
.feat-card {
  background:rgba(15, 61, 58, 0.55);border:1px solid rgba(245, 218, 191, 0.15);border-radius:14px;padding:22px 20px;
  position:relative;overflow:hidden;transition:all 0.25s ease;
}
.feat-card:hover { transform:translateY(-3px);box-shadow:0 20px 50px rgba(7, 26, 24, 0.5);border-color:rgba(245, 218, 191, 0.35); }
.feat-card::before { content:'';position:absolute;top:0;left:0;right:0;height:2px; }
.fc-blue::before   { background:linear-gradient(90deg,transparent,#6C151E,transparent); }
.fc-violet::before { background:linear-gradient(90deg,transparent,#0F3D3A,transparent); }
.fc-cyan::before   { background:linear-gradient(90deg,transparent,#F5DABF,transparent); }
.feat-card-title { font-size:1rem;font-weight:700;color:#FFF5EB;margin-bottom:6px;letter-spacing:-0.01em; }
.feat-card-desc  { font-size:0.8rem;color:rgba(245, 218, 191, 0.75);line-height:1.5; }
.feat-card-arrow { position:absolute;bottom:18px;right:18px;font-size:1rem;color:rgba(245, 218, 191, 0.6);transition:transform 0.2s; }
.feat-card:hover .feat-card-arrow { transform:translate(3px,-3px);color:#F5DABF; }

/* SELECTBOX */
[data-testid="stSelectbox"] label { color: #F5DABF !important; }
[data-testid="stSelectbox"] > div > div { background: rgba(11, 39, 37, 0.95) !important; border-color: rgba(245, 218, 191, 0.25) !important; color: #F5DABF !important; }

/* MISC & GLOBAL TYPOGRAPHY */
hr { border-color: rgba(245, 218, 191, 0.1) !important; }
h1,h2,h3,h4,h5,h6 { color: #FFF5EB !important; -webkit-text-fill-color: #FFF5EB !important; }
p  { color: #F5DABF; }
li { color: #F5DABF; }
[data-testid="stMarkdownContainer"] p { color: #F5DABF; }
[data-testid="stMarkdownContainer"] span { color: inherit; }
.stMarkdown p { color: #F5DABF; }
code { font-family:'JetBrains Mono',monospace !important; background:rgba(5, 19, 18, 0.9) !important; border:1px solid rgba(245, 218, 191, 0.18) !important; border-radius:4px !important; color:#F5DABF !important; padding:1px 5px !important; }
pre  { background:rgba(5, 19, 18, 0.9) !important; border:1px solid rgba(245, 218, 191, 0.18) !important; border-radius:6px !important; color:#F5DABF !important; }
::-webkit-scrollbar { width:4px; height:4px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:rgba(245, 218, 191, 0.2); border-radius:2px; }
::-webkit-scrollbar-thumb:hover { background:rgba(245, 218, 191, 0.35); }
@media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation-duration:0.01ms !important; transition-duration:0.01ms !important; } }
</style>
""", unsafe_allow_html=True)
# =============================================================================
# SESSION STATE & CONSTANTS
# =============================================================================
def _init():
    defs = {
        "sid":        str(uuid.uuid4())[:8],
        "last":       None,
        "plan":       None,
        "tok":        None,
        "cmd":        "",
        "nav":        "command_centre",
    }
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v
_init()

SICON = {
    "done":"✓","failed":"✗","pending":"○","pending_approval":"⏸",
    "running":"◉","denied":"⊘","info":"·","success":"✓","error":"✗",
    "warning":"!","skipped":"›",
}
SBADGE = {
    "done":"b-done","success":"b-done","failed":"b-failed","error":"b-failed",
    "pending":"b-pending","pending_approval":"b-pending","running":"b-running",
    "denied":"b-denied","info":"b-info","warning":"b-warn2","skipped":"b-skip",
}
SDOT = {
    "pending":"sn-pending","pending_approval":"sn-approval","done":"sn-done",
    "failed":"sn-failed","running":"sn-running","skipped":"sn-skipped","denied":"sn-denied",
}
NAV = [
    ("command_centre",  "⌘", "Command Centre"),
    ("tasks_plans",     "☰", "Tasks & Plans"),
    ("exec_history",    "⏱", "Execution History"),
    ("system_monitor",  "◈", "System Monitor"),
    ("security_centre", "⚿", "Security Centre"),
    ("memory_context",  "◫", "Memory & Context"),
    ("settings",        "⚙", "Settings"),
]
PIPE_STAGES = [
    ("🔍","UNDERSTAND"),("📋","PLAN"),("🔒","SECURE"),
    ("⚡","EXECUTE"),("📡","MONITOR"),("✅","VERIFY"),("🔄","RECOVER"),
]


# =============================================================================
# HELPERS
# =============================================================================
def badge(status: str, label: str = "") -> str:
    cls  = SBADGE.get(status, "b-info")
    txt  = html.escape(label or status.replace("_", " "))
    return f'<span class="badge {cls}"><span class="badge-dot"></span>{txt}</span>'


def sec_hdr(title: str, right: str = "", color: str = "blue"):
    cc = "sec-title-v" if color == "violet" else ("sec-title-c" if color == "cyan" else "")
    rh = f'<span style="font-size:0.7rem;color:#F5DABF;">{html.escape(right)}</span>' if right else ""
    st.markdown(f'<div class="sec-hdr"><span class="sec-title {cc}">{html.escape(title)}</span>{rh}</div>', unsafe_allow_html=True)


def empty_state(icon: str, title: str, desc: str = ""):
    dh = f'<div class="empty-st-desc">{html.escape(desc)}</div>' if desc else ""
    st.markdown(f'<div class="empty-st"><div class="empty-st-icon">{icon}</div><div class="empty-st-title">{html.escape(title)}</div>{dh}</div>', unsafe_allow_html=True)


def render_pipeline(result):
    """Render UNDERSTAND→PLAN→SECURE→EXECUTE→MONITOR→VERIFY→RECOVER pipeline."""
    if not result:
        states = ["pending"] * 7
    else:
        s = result.get("status", "pending")
        steps = result.get("steps", [])
        has_steps = bool(steps)
        any_run  = any(st2.get("status") in ("running","done","failed") for st2 in steps)
        any_done = any(st2.get("status") == "done" for st2 in steps)
        any_fail = any(st2.get("status") == "failed" for st2 in steps)
        denied   = s == "denied"

        if s == "pending_approval":
            states = ["done","done","running","pending","pending","pending","pending"]
        elif denied:
            states = ["done","done","failed","pending","pending","pending","pending"]
        elif s == "done":
            states = ["done","done","done","done","done","done","pending"]
        elif s == "failed":
            states = ["done","done","done","failed" if any_fail else "done","pending","pending","running"]
        elif has_steps and any_run:
            states = ["done","done","done","running","pending","pending","pending"]
        else:
            states = ["done","done","pending","pending","pending","pending","pending"]

    html_parts = []
    for i, ((ic, lbl), st2) in enumerate(zip(PIPE_STAGES, states)):
        css = f"ps-{st2}"
        html_parts.append(f'<div class="pipe-stage {css}"><div class="pipe-icon">{ic}</div><div class="pipe-label">{lbl}</div></div>')
        if i < len(PIPE_STAGES) - 1:
            clr = "rgba(61,213,152,0.35)" if st2 == "done" else "rgba(15,61,58,0.4)"
            html_parts.append(f'<div class="pipe-connector" style="background:{clr};"></div>')
    st.markdown(f'<div class="pipeline">{"".join(html_parts)}</div>', unsafe_allow_html=True)


def render_steps(steps: list):
    if not steps:
        empty_state("◈", "No steps", "The plan contained no steps to execute.")
        return
    for s in steps:
        status  = s.get("status","pending")
        dot_cls = SDOT.get(status, "sn-pending")
        icon    = SICON.get(status, "○")
        tool    = html.escape(str(s.get("tool","")))
        desc    = html.escape(str(s.get("description","")))
        err     = s.get("error","")
        eh = f'<div class="step-err">↳ {html.escape(str(err))}</div>' if err else ""
        st.markdown(f"""
<div class="step-row">
  <div class="step-num {dot_cls}">{icon}</div>
  <div class="step-body">
    <div class="step-hdr"><span class="step-desc">{desc}</span>{badge(status)}</div>
    <span class="step-tool">{tool}</span>{eh}
  </div>
</div>""", unsafe_allow_html=True)


def render_terminal(output):
    """Render output in terminal style."""
    if output is None:
        st.markdown('<div class="terminal"><span class="term-muted">// no output</span></div>', unsafe_allow_html=True)
        return
    if isinstance(output, str):
        lines = output.splitlines() if output else [""]
        rows  = "".join(f'<div class="term-line">{html.escape(ln)}</div>' for ln in lines)
        st.markdown(f'<div class="terminal"><span class="term-prompt">$ output</span>\n{rows}</div>', unsafe_allow_html=True)
        return
    if isinstance(output, dict):
        if "content" in output:
            hdr  = f'<div class="term-line term-info">// {html.escape(output.get("path",""))} · {output.get("size_bytes",0)} bytes</div>'
            body = "".join(f'<div class="term-line">{html.escape(ln)}</div>' for ln in str(output["content"]).splitlines())
            st.markdown(f'<div class="terminal">{hdr}{body}</div>', unsafe_allow_html=True)
        elif "bytes_written" in output:
            st.markdown(f'<div class="terminal"><div class="term-line term-ok">✓ File written: {html.escape(output.get("path",""))} ({output["bytes_written"]} bytes)</div></div>', unsafe_allow_html=True)
        elif "files" in output:
            files = output.get("files",[])
            if files:
                rows = "".join(f'<div class="term-line"><span class="term-info">  {html.escape(f["name"])}</span><span class="term-muted">  {f["size_bytes"]} B</span></div>' for f in files)
                st.markdown(f'<div class="terminal"><div class="term-line term-prompt">$ ls workspace/</div>{rows}<div class="term-line term-muted">// {len(files)} file(s)</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="terminal"><span class="term-muted">// workspace is empty</span></div>', unsafe_allow_html=True)
        elif "platform" in output:
            rows = "".join(f'<div class="term-line"><span class="term-info">{html.escape(k)}</span><span class="term-muted"> = </span><span>{html.escape(str(v))}</span></div>' for k, v in output.items())
            st.markdown(f'<div class="terminal"><div class="term-line term-prompt">$ system info</div>{rows}</div>', unsafe_allow_html=True)
        elif "workspace" in output and "shell_execution" in output:
            rows = ""
            for k, v in output.items():
                vl   = str(v) if not isinstance(v, list) else ", ".join(v)
                vcls = "term-err" if vl in ("DISABLED","REJECTED") else ("term-ok" if vl == "ENFORCED" else "term-info")
                rows += f'<div class="term-line"><span class="term-muted">{html.escape(k)}</span><span class="term-muted"> = </span><span class="{vcls}">{html.escape(vl)}</span></div>'
            st.markdown(f'<div class="terminal"><div class="term-line term-prompt">$ security policy</div>{rows}</div>', unsafe_allow_html=True)
        else:
            st.json(output)
    elif isinstance(output, list):
        rows = "".join(f'<div class="term-line"><span class="term-muted">{html.escape(str(e.get("timestamp",""))[-8:])}</span>  <span>{html.escape(str(e.get("action","")))}</span></div>' for e in output[:30])
        st.markdown(f'<div class="terminal"><div class="term-line term-prompt">$ activity log</div>{rows}</div>', unsafe_allow_html=True)
    else:
        st.json(output)


def render_logs(entries: list):
    for e in entries:
        ts  = html.escape(str(e.get("timestamp",""))[-8:])
        act = html.escape(str(e.get("action","")))
        cat = html.escape(str(e.get("category","")))
        s   = e.get("status","info")
        ic  = SICON.get(s,"·")
        st.markdown(f'<div class="log-row"><div class="log-ts">{ts}</div><div class="log-icon">{ic}</div><div class="log-action">{act}</div><div class="log-cat">{cat}</div></div>', unsafe_allow_html=True)
# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.markdown("""
<div class="nav-brand">
  <div class="nav-logo">🧠 <span>Sentient</span>OS</div>
  <div class="nav-tagline">AI-Native Operating Environment</div>
  <div class="nav-version">◉ v1.0 · ACTIVE</div>
</div>""", unsafe_allow_html=True)

    if st.session_state.get("nav") != "command_centre":
        if st.button("←  Back to Start Page", key="sidebar_back_to_start", use_container_width=True):
            st.session_state["nav"] = "command_centre"
            st.rerun()
        st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

    st.markdown('<div class="nav-section-label">Core</div>', unsafe_allow_html=True)
    for _key, _ic, _lbl in NAV[:4]:
        if st.button(f"{_ic}  {_lbl}", key=f"nav_{_key}", use_container_width=True):
            st.session_state["nav"] = _key
            st.rerun()

    st.markdown('<div class="nav-section-label">System</div>', unsafe_allow_html=True)
    for _key, _ic, _lbl in NAV[4:]:
        if st.button(f"{_ic}  {_lbl}", key=f"nav_{_key}", use_container_width=True):
            st.session_state["nav"] = _key
            st.rerun()

    st.markdown("---")
    _ws   = get_workspace_summary()
    _tk   = db.get_tasks(limit=100)
    _pend = [t for t in _tk if t["status"] == "pending_approval"]
    _c1, _c2 = st.columns(2)
    with _c1:
        st.markdown(f"""
<div class="metric-card" style="padding:11px 10px;">
  <div class="metric-val" style="font-size:1.45rem;">{_ws['file_count']}</div>
  <div class="metric-label" style="font-size:0.6rem;">Workspace Files</div>
</div>""", unsafe_allow_html=True)
    with _c2:
        _pc = "#FBBF24" if _pend else "#8E1F2A"
        st.markdown(f"""
<div class="metric-card" style="padding:11px 10px;">
  <div class="metric-val" style="font-size:1.45rem;background:linear-gradient(135deg,{_pc},{_pc});-webkit-background-clip:text;">{len(_pend)}</div>
  <div class="metric-label" style="font-size:0.6rem;">Pending Approvals</div>
</div>""", unsafe_allow_html=True)

    _m = get_system_metrics()
    st.markdown(f"""
<div class="sidebar-footer">
  <span class="online-dot"></span><span style="color:#3DD598;font-weight:600;">Connected</span><br>
  <span style="color:rgba(245,218,191,0.5);">Session</span>&nbsp;<code>{html.escape(st.session_state['sid'])}</code><br>
  <span style="color:rgba(245,218,191,0.5);">Workspace</span>&nbsp;<code>./workspace</code><br>
  <span style="color:rgba(245,218,191,0.5);">{html.escape(_m['platform'])} · {html.escape(_m['python_version'])}</span>
</div>""", unsafe_allow_html=True)


# =============================================================================
# TOP STATUS BAR
# =============================================================================
_mt   = get_system_metrics()
_wt   = get_workspace_summary()
_now  = datetime.now().strftime("%H:%M")
_lr   = st.session_state.get("last")
_pktk = db.get_tasks(limit=50)
_pk   = [t for t in _pktk if t["status"] == "pending_approval"]

_ag_st  = "Waiting Approval" if (_lr and _lr.get("status") == "pending_approval") else "Idle"
_ag_dot = "dot-warn" if _ag_st != "Idle" else "dot-ok"
_pk_html= (f'<span style="color:#F5DABF;font-weight:600;">{len(_pk)} pending</span>'
           if _pk else '<span style="color:#3DD598;">None</span>')

st.markdown(f"""
<div class="status-bar">
  <div class="status-pill">
    <div class="status-dot {_ag_dot}"></div>
    <span class="status-label">Agent</span>
    <span class="status-val">{html.escape(_ag_st)}</span>
  </div>
  <span class="status-div">|</span>
  <div class="status-pill">
    <div class="status-dot dot-blue"></div>
    <span class="status-label">Workspace</span>
    <span class="status-val">./workspace</span>
    <span style="color:rgba(245,218,191,0.4);font-size:0.68rem;">({_wt['file_count']} files)</span>
  </div>
  <span class="status-div">|</span>
  <span class="status-label">Approvals:</span>{_pk_html}
  <span class="status-div">|</span>
  <div class="status-pill">
    <div class="status-dot dot-ok"></div>
    <span class="status-label">Health</span>
    <span class="status-val">Nominal</span>
  </div>
  <span style="flex:1;"></span>
  <div class="status-pill" style="background:rgba(15,61,58,0.4);border-color:rgba(245,218,191,0.15);">
    <span style="font-family:'JetBrains Mono',monospace;color:#8ED8D2;font-size:0.7rem;">{html.escape(_mt['platform'])} · {_now}</span>
  </div>
</div>
""", unsafe_allow_html=True)

_nav = st.session_state["nav"]

# GLOBAL BACK-TO-START TOP BAR (visible on all sub-pages)
if _nav != "command_centre":
    _nav_titles = {
        "tasks_plans": "Tasks & Plans",
        "exec_history": "Execution History",
        "system_monitor": "System Monitor",
        "security_centre": "Security Centre",
        "memory_context": "Memory & Context",
        "settings": "Settings",
    }
    _page_name = _nav_titles.get(_nav, _nav.replace("_", " ").title())
    _bcol1, _bcol2 = st.columns([2.5, 7.5])
    with _bcol1:
        if st.button("←  Back to Start Page", key="global_top_back_btn", use_container_width=True):
            st.session_state["nav"] = "command_centre"
            st.rerun()
    with _bcol2:
        st.markdown(f'''
<div style="display:flex;align-items:center;height:100%;min-height:42px;font-size:0.84rem;color:rgba(245,218,191,0.65);font-family:'Inter',sans-serif;">
  <span style="color:#F5DABF;font-weight:600;">Command Centre</span>
  <span style="margin:0 10px;opacity:0.4;">/</span>
  <span style="color:#FFF5EB;font-weight:700;">{html.escape(_page_name)}</span>
</div>''', unsafe_allow_html=True)
    st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

# =============================================================================
# COMMAND CENTRE
# =============================================================================
if _nav == "command_centre":
    st.markdown("""
<div class="page-header">
  <div class="page-title">Command Centre</div>
  <div class="page-subtitle">Turn your goals into actions.</div>
</div>""", unsafe_allow_html=True)

    # AI ORB + COMMAND HERO
    st.markdown("""
<div class="cmd-hero">
  <div style="display:flex;align-items:flex-start;gap:24px;flex-wrap:wrap;">
    <div style="flex:0 0 auto;display:flex;flex-direction:column;align-items:center;">
      <div class="orb-container">
        <div class="orb-glow"></div>
        <div class="orb-ring2"></div>
        <div class="orb-ring"></div>
        <div class="orb"></div>
      </div>
      <div style="font-size:0.6rem;color:rgba(245,218,191,0.5);text-transform:uppercase;letter-spacing:0.12em;text-align:center;">
        AI ENGINE<br>ONLINE
      </div>
    </div>
    <div style="flex:1;min-width:240px;">
      <div class="cmd-title">Command Centre</div>
      <div class="cmd-sub">Describe your goal in plain language. SentientOS will plan, secure, execute, and verify.</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">
        <span class="chip">⌘K Quick command</span>
        <span class="chip">↵ to execute</span>
        <span class="chip">? for help</span>
      </div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    with st.form("cmd_form", clear_on_submit=False):
        _user_cmd = st.text_input(
            "Goal",
            value=st.session_state.get("cmd",""),
            placeholder="e.g. read notes.txt  ·  list workspace files  ·  create file report.txt  ·  show system status",
            label_visibility="collapsed",
        )
        _c1, _c2, _c3 = st.columns([5, 1, 1])
        with _c1:
            _sub = st.form_submit_button("⚡  Execute Goal", use_container_width=True)
        with _c2:
            _clr = st.form_submit_button("✕ Clear", use_container_width=True)
        with _c3:
            _hlp = st.form_submit_button("? Help", use_container_width=True)

    # Example chips
    st.markdown('<div style="display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 6px;">', unsafe_allow_html=True)
    with st.expander("⊞  Example commands", expanded=False):
        _ecols = st.columns(3)
        for _i, _c_ in enumerate(DEMO_COMMANDS):
            with _ecols[_i % 3]:
                if st.button(f"▷ {_c_}", key=f"ex_{_i}", use_container_width=True):
                    st.session_state["cmd"] = _c_
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    if _clr:
        st.session_state.update({"last":None,"plan":None,"tok":None,"cmd":""})
        st.rerun()
    if _hlp:
        st.session_state["cmd"] = "help"
        st.rerun()

    if _sub and _user_cmd.strip():
        st.session_state["cmd"] = _user_cmd
        _plan = parse_command(_user_cmd)
        db.log_activity(st.session_state["sid"], f"Goal: '{_user_cmd}'", category="user", status="info")
        _res = execute_plan(_plan, session_id=st.session_state["sid"], approval_token=None)
        st.session_state["last"] = _res
        if _res["status"] == "pending_approval":
            st.session_state["plan"] = _plan
            st.session_state["tok"]  = _res.get("approval_token")
        else:
            st.session_state["plan"] = None
            st.session_state["tok"]  = None
        st.rerun()

    _res = st.session_state.get("last")

    # PIPELINE (always shown, dim when no result)
    st.markdown("---")
    sec_hdr("Execution Pipeline")
    st.markdown('<div class="glass-card" style="padding:8px 14px;">', unsafe_allow_html=True)
    render_pipeline(_res)
    st.markdown("</div>", unsafe_allow_html=True)

    if _res:
        _status  = _res["status"]
        _message = _res.get("message","")
        _steps   = _res.get("steps",[])
        _output  = _res.get("output")

        _sc = {"done":"#3DD598","failed":"#FF6B7A","denied":"#FF6B7A","pending_approval":"#FBBF24"}.get(_status,"#8E1F2A")

        st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;padding:14px 0 10px;">
  <div>
    <span style="font-size:1.05rem;font-weight:700;color:{_sc};">
      {SICON.get(_status,'○')} {_status.replace('_',' ').title()}
    </span>
    <div style="font-size:0.8rem;color:#F5DABF;margin-top:2px;">{html.escape(_message)}</div>
  </div>
  {badge(_status)}
</div>""", unsafe_allow_html=True)

        _cl, _cr = st.columns([5, 4])
        with _cl:
            sec_hdr("Execution Timeline", f"{len(_steps)} steps")
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            render_steps(_steps)
            st.markdown("</div>", unsafe_allow_html=True)
        with _cr:
            sec_hdr("Terminal Output", color="cyan")
            render_terminal(_output)

        # APPROVAL PANEL
        if _status == "pending_approval" and st.session_state.get("plan"):
            st.markdown("""
<div class="approval-card">
  <div class="approval-title">⏸ Human Approval Required</div>
  <p style="font-size:0.82rem;color:#F5DABF;margin:0 0 6px;">
    This action will modify system state. Review the request carefully before approving.
  </p>""", unsafe_allow_html=True)
            _pstep = _res.get("pending_step")
            if _pstep:
                st.markdown(f"""
  <div class="approval-detail">
    <span style="color:#F5DABF;">Tool:</span> {html.escape(str(_pstep.tool))}<br>
    <span style="color:#F5DABF;">Params:</span> {html.escape(str(_pstep.params))}<br>
    <span style="color:#FF6B7A;">⚠ This operation writes to disk and cannot be undone automatically.</span>
  </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            _aa, _ad = st.columns(2)
            with _aa:
                if st.button("✓  Approve & Execute", key="approve_btn", use_container_width=True):
                    _tok = st.session_state.get("tok")
                    if _tok:
                        _r2 = execute_plan(st.session_state["plan"], session_id=st.session_state["sid"], approval_token=_tok)
                        st.session_state.update({"last":_r2,"plan":None,"tok":None})
                        st.rerun()
                    else:
                        st.error("No valid approval token. Please re-submit the command.")
            with _ad:
                if st.button("✗  Deny", key="deny_btn", use_container_width=True):
                    _tok = st.session_state.get("tok")
                    if _tok:
                        from sentientos.security import revoke_approval_ticket
                        revoke_approval_ticket(_tok)
                    st.session_state.update({
                        "last":{"status":"denied","message":"Action denied by user.","steps":_steps,"output":None},
                        "plan":None,"tok":None,
                    })
                    db.log_activity(st.session_state["sid"],"User denied pending approval.","security","warning")
                    st.rerun()
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        _cc_c1, _cc_c2 = st.columns([2.5, 7.5])
        with _cc_c1:
            if st.button("←  Back to Start Page", key="cc_res_back_to_start", use_container_width=True):
                st.session_state.update({"last": None, "plan": None, "tok": None, "cmd": ""})
                st.rerun()
    else:
        # No result yet — show empty execution panel
        st.markdown("---")
        _cl2, _cr2 = st.columns([5, 4])
        with _cl2:
            sec_hdr("Execution Timeline")
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            empty_state("◈","Awaiting command","Enter a goal above and press Execute.")
            st.markdown("</div>", unsafe_allow_html=True)
        with _cr2:
            sec_hdr("Terminal Output", color="cyan")
            st.markdown('<div class="terminal"><span class="term-muted">// ready — awaiting input</span><br><span class="term-prompt">$ _</span></div>', unsafe_allow_html=True)

    # FEATURE CARDS
    st.markdown("---")
    _fc1, _fc2, _fc3 = st.columns(3)
    with _fc1:
        st.markdown("""
<div class="feat-card fc-blue">
  <div class="feat-card-icon">📋</div>
  <div class="feat-card-title">Tasks &amp; Plans</div>
  <div class="feat-card-desc">View the current task plan, step breakdown, and intent classification.</div>
  <div class="feat-card-arrow">↗</div>
</div>""", unsafe_allow_html=True)
        if st.button("Open Tasks", key="fc_tasks", use_container_width=True):
            st.session_state["nav"] = "tasks_plans"
            st.rerun()
    with _fc2:
        st.markdown("""
<div class="feat-card fc-violet">
  <div class="feat-card-icon">⏱</div>
  <div class="feat-card-title">Execution History</div>
  <div class="feat-card-desc">Browse past runs, outcomes, step logs, and error reports.</div>
  <div class="feat-card-arrow">↗</div>
</div>""", unsafe_allow_html=True)
        if st.button("Open History", key="fc_hist", use_container_width=True):
            st.session_state["nav"] = "exec_history"
            st.rerun()
    with _fc3:
        st.markdown("""
<div class="feat-card fc-cyan">
  <div class="feat-card-icon">◫</div>
  <div class="feat-card-title">Memory &amp; Context</div>
  <div class="feat-card-desc">Session state, workspace context, and execution memory.</div>
  <div class="feat-card-arrow">↗</div>
</div>""", unsafe_allow_html=True)
        if st.button("Open Memory", key="fc_mem", use_container_width=True):
            st.session_state["nav"] = "memory_context"
            st.rerun()
# =============================================================================
# TASKS & PLANS
# =============================================================================
elif _nav == "tasks_plans":
    st.markdown('<div class="page-header"><div class="page-title">Tasks &amp; Plans</div><div class="page-subtitle">Active task state and current execution plan.</div></div>', unsafe_allow_html=True)
    _res = st.session_state.get("last")
    if _res:
        _s2 = _res["status"]
        _steps2 = _res.get("steps",[])
        _cmd2 = html.escape(st.session_state.get("cmd",""))
        st.markdown(f"""
<div class="glass-card">
  <div class="card-title">Active Goal</div>
  <div style="font-size:0.95rem;color:#FFF5EB;margin-bottom:10px;">{_cmd2}</div>
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <div style="font-size:0.8rem;color:#F5DABF;">{html.escape(_res.get('message',''))}</div>
    {badge(_s2)}
  </div>
</div>""", unsafe_allow_html=True)
        sec_hdr("Execution Pipeline")
        st.markdown('<div class="glass-card" style="padding:8px 14px;">', unsafe_allow_html=True)
        render_pipeline(_res)
        st.markdown("</div>", unsafe_allow_html=True)
        sec_hdr("Step Timeline", f"{len(_steps2)} steps")
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        render_steps(_steps2)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        empty_state("⌘","No active task","Execute a command in Command Centre to see the plan here.")


# =============================================================================
# EXECUTION HISTORY
# =============================================================================
elif _nav == "exec_history":
    st.markdown('<div class="page-header"><div class="page-title">Execution History</div><div class="page-subtitle">All recorded tasks, outcomes, and execution details.</div></div>', unsafe_allow_html=True)
    _tasks = db.get_tasks(limit=100)
    if not _tasks:
        empty_state("⏱","No history yet","Completed tasks will appear here.")
    else:
        _hf1, _hf2 = st.columns([3,1])
        with _hf1:
            _sf = st.selectbox("Filter",["all","done","failed","pending_approval","denied"],label_visibility="collapsed")
        with _hf2:
            _hl = st.selectbox("Show",[10,25,50],label_visibility="collapsed")
        if _sf != "all":
            _tasks = [t for t in _tasks if t["status"] == _sf]
        _tasks = _tasks[:_hl]
        st.markdown(f'<p style="font-size:0.74rem;color:#F5DABF;margin-bottom:10px;">Showing {len(_tasks)} tasks</p>', unsafe_allow_html=True)
        for t in _tasks:
            _ts = t["status"]; _ic2 = SICON.get(_ts,"·")
            _up = str(t.get("updated_at",""))[:19]
            with st.expander(f"{_ic2}  {t['command'][:68]}  ·  {_up[:16]}", expanded=False):
                _eh1, _eh2 = st.columns(2)
                with _eh1:
                    st.markdown(f"**Task ID:** `{html.escape(str(t.get('task_id','')))}` ")
                    st.markdown(f"**Session:** `{html.escape(str(t.get('session_id','')))}` ")
                    st.markdown(f"**Created:** {html.escape(str(t.get('created_at',''))[:19])}")
                with _eh2:
                    st.markdown(f"**Status:** {badge(_ts)}", unsafe_allow_html=True)
                    if t.get("result"):
                        st.markdown(f"**Result:** {html.escape(str(t['result'])[:200])}")


# =============================================================================
# SYSTEM MONITOR
# =============================================================================
elif _nav == "system_monitor":
    st.markdown('<div class="page-header"><div class="page-title">System Monitor</div><div class="page-subtitle">Real runtime metrics only — no fabricated values.</div></div>', unsafe_allow_html=True)
    _met = get_system_metrics()
    _ws2 = get_workspace_summary()
    sec_hdr("Runtime Environment")
    _sm1, _sm2, _sm3, _sm4 = st.columns(4)
    for _mc, _ml, _mv in [
        (_sm1,"Platform",_met["platform"]),
        (_sm2,"Python",_met["python_version"]),
        (_sm3,"Architecture",_met["arch"]),
        (_sm4,"Host",_met["node"][:14]),
    ]:
        with _mc:
            st.markdown(f"""
<div class="metric-card">
  <div class="metric-val" style="font-size:1rem;word-break:break-all;">{html.escape(_mv)}</div>
  <div class="metric-label">{_ml}</div>
</div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    sec_hdr("CPU · Memory · Disk · Network")
    _r1, _r2, _r3, _r4 = st.columns(4)
    for _mc2, _ml2 in [(_r1,"CPU"),(_r2,"Memory"),(_r3,"Disk"),(_r4,"Network")]:
        with _mc2:
            st.markdown(f"""
<div class="metric-card">
  <div class="metric-val" style="font-size:0.9rem;color:#F5DABF;-webkit-text-fill-color:#F5DABF;">N/A</div>
  <div class="metric-label">{_ml2}</div>
  <div style="font-size:0.6rem;color:rgba(245,218,191,0.3);margin-top:3px;">Add psutil for live data</div>
</div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    _mw1, _mw2 = st.columns(2)
    with _mw1:
        st.markdown(f"""
<div class="glass-card">
  <div class="card-title">Workspace</div>
  <div class="p-row"><span class="p-key">Status</span><span class="{'p-ok' if _ws2['exists'] else 'p-warn'}">{'Available' if _ws2['exists'] else 'Not found'}</span></div>
  <div class="p-row"><span class="p-key">Files (allowed types)</span><span class="p-info">{_ws2['file_count']}</span></div>
  <div class="p-row"><span class="p-key">Total size</span><span class="p-info">{_ws2['total_bytes']} bytes</span></div>
  <div class="p-row"><span class="p-key">Path</span><span class="p-info">./workspace</span></div>
</div>""", unsafe_allow_html=True)
    with _mw2:
        st.markdown("""
<div class="glass-card">
  <div class="card-title card-title-c">Security Sandbox</div>
  <div class="p-row"><span class="p-key">Shell execution</span><span class="p-warn">DISABLED</span></div>
  <div class="p-row"><span class="p-key">Network access</span><span class="p-warn">DISABLED</span></div>
  <div class="p-row"><span class="p-key">Code evaluation</span><span class="p-warn">DISABLED</span></div>
  <div class="p-row"><span class="p-key">Sandbox status</span><span class="p-ok">ACTIVE</span></div>
  <div class="p-row"><span class="p-key">Approval binding</span><span class="p-ok">ENFORCED</span></div>
</div>""", unsafe_allow_html=True)
# =============================================================================
# SECURITY CENTRE
# =============================================================================
elif _nav == "security_centre":
    st.markdown('<div class="page-header"><div class="page-title">Security Centre</div><div class="page-subtitle">Active policies, approval queue, blocked operations, and audit trail.</div></div>', unsafe_allow_html=True)
    _pol  = describe_policy()
    _alll = db.get_recent_activity(limit=200)
    _secl = [l for l in _alll if l.get("category") == "security"]

    st.markdown("""
<div class="glass-card" style="border-color:rgba(251,75,100,0.18);background:rgba(251,75,100,0.018);">
  <div class="card-title" style="color:#FF6B7A;">⚿ Security Gateway — Active &amp; Enforced</div>
  <p style="font-size:0.82rem;color:#F5DABF;margin:0;">
    Every tool call is validated by an independent security module. The planner cannot bypass it.
    Approval tickets are cryptographically bound to exact parameters and are single-use.
  </p>
</div>""", unsafe_allow_html=True)

    _sc1, _sc2 = st.columns(2)
    with _sc1:
        sec_hdr("Security Policy", color="cyan")
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        for _k, _v in _pol.items():
            _vs = ", ".join(_v) if isinstance(_v, list) else str(_v)
            _vc = "p-warn" if _vs in ("DISABLED","REJECTED") else ("p-ok" if _vs == "ENFORCED" else "p-info")
            st.markdown(f'<div class="p-row"><span class="p-key">{html.escape(_k.replace("_"," ").title())}</span><span class="{_vc}">{html.escape(_vs)}</span></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with _sc2:
        sec_hdr("Blocked Operations")
        _blocked = [
            ("⊘","err","Shell command execution"),
            ("⊘","err","Arbitrary code evaluation"),
            ("⊘","err","Network / internet access"),
            ("⊘","err","Absolute file paths"),
            ("⊘","err","Path traversal (../)"),
            ("⊘","err","Windows drive & UNC paths"),
            ("⊘","err","Symlink workspace escapes"),
            ("⊘","err","Non-text file types (.py, .sh, .exe)"),
            ("⊘","err","Files > 64 KB"),
            ("⏸","warn","Writes without approval token"),
            ("⏸","warn","Log clearing without approval"),
            ("⏸","warn","Tampered or reused tickets"),
        ]
        _clrm = {"err":"#FF6B7A","warn":"#FBBF24"}
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        for _bic, _bck, _bitm in _blocked:
            st.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding:5px 0;border-bottom:1px solid rgba(245,218,191,0.08);"><span style="color:{_clrm[_bck]};width:16px;text-align:center;flex-shrink:0;">{_bic}</span><span style="font-size:0.8rem;color:#F5DABF;">{html.escape(_bitm)}</span></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    sec_hdr("Security Audit Log", f"{len(_secl)} events", color="cyan")
    if not _secl:
        empty_state("⚿","No security events yet","Events appear here as commands execute.")
    else:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        render_logs(_secl[:50])
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    sec_hdr("Full Activity Log")
    _lf1, _lf2 = st.columns([3,1])
    with _lf1:
        _catf = st.selectbox("Category",["all","user","planner","executor","security","general"],label_visibility="collapsed")
    with _lf2:
        _llim = st.selectbox("Entries",[25,50,100],label_visibility="collapsed")
    _lf = _alll if _catf == "all" else [l for l in _alll if l.get("category") == _catf]
    _lf = _lf[:_llim]
    if not _lf:
        empty_state("·","No log entries","")
    else:
        st.markdown(f'<p style="font-size:0.72rem;color:#F5DABF;margin-bottom:8px;">Showing {len(_lf)} entries</p>', unsafe_allow_html=True)
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        render_logs(_lf)
        st.markdown("</div>", unsafe_allow_html=True)

    if st.button("✕  Trim log (keep last 200 entries)", key="trim_log_btn"):
        db.clear_old_logs(keep=200)
        db.log_activity(st.session_state["sid"],"Activity log trimmed","general","info")
        st.success("Log trimmed.")
        st.rerun()


# =============================================================================
# MEMORY & CONTEXT
# =============================================================================
elif _nav == "memory_context":
    st.markdown('<div class="page-header"><div class="page-title">Memory &amp; Context</div><div class="page-subtitle">Session state, workspace context, and execution history.</div></div>', unsafe_allow_html=True)
    _mm1, _mm2 = st.columns(2)
    with _mm1:
        sec_hdr("Session State")
        _sess = {
            "Session ID":     st.session_state.get("sid",""),
            "Last Command":   st.session_state.get("cmd","") or "(none)",
            "Last Status":    (st.session_state.get("last") or {}).get("status","none"),
            "Pending Plan":   "Yes" if st.session_state.get("plan") else "No",
            "Approval Token": "Present" if st.session_state.get("tok") else "None",
        }
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        for _k, _v in _sess.items():
            st.markdown(f'<div class="p-row"><span class="p-key">{html.escape(_k)}</span><span class="p-info">{html.escape(str(_v))}</span></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with _mm2:
        sec_hdr("Task Summary", color="violet")
        _tms = db.get_tasks(limit=100)
        _tmd = sum(1 for t in _tms if t["status"]=="done")
        _tmf = sum(1 for t in _tms if t["status"]=="failed")
        _tmp = sum(1 for t in _tms if t["status"]=="pending_approval")
        st.markdown(f"""
<div class="glass-card">
  <div class="p-row"><span class="p-key">Total tasks</span><span class="p-info">{len(_tms)}</span></div>
  <div class="p-row"><span class="p-key">Completed</span><span class="p-ok">{_tmd}</span></div>
  <div class="p-row"><span class="p-key">Failed</span><span class="{'p-warn' if _tmf else 'p-info'}">{_tmf}</span></div>
  <div class="p-row"><span class="p-key">Pending approval</span><span class="{'p-cyan' if _tmp else 'p-info'}">{_tmp}</span></div>
</div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    sec_hdr("Workspace Files", color="cyan")
    from sentientos.tools import tool_list_workspace
    _wsl2 = tool_list_workspace()
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    if _wsl2.get("success") and _wsl2["data"].get("files"):
        for _f2 in _wsl2["data"]["files"]:
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(245,218,191,0.08);font-size:0.82rem;"><span style="color:#F5DABF;font-family:\'JetBrains Mono\',monospace;">{html.escape(_f2["name"])}</span><span style="color:#8E1F2A;">{_f2["size_bytes"]} B</span></div>', unsafe_allow_html=True)
    else:
        empty_state("◌","Workspace is empty","No files with allowed extensions found.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    sec_hdr("Recent Execution Context")
    _rec = db.get_tasks(limit=6)
    if _rec:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        for t in _rec:
            st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(245,218,191,0.08);"><div><div style="font-size:0.83rem;color:#FFF5EB;">{html.escape(str(t["command"])[:65])}</div><div style="font-size:0.69rem;color:#F5DABF;margin-top:2px;">{html.escape(str(t.get("updated_at",""))[:19])}</div></div>{badge(t["status"])}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        empty_state("◫","No previous context","")


# =============================================================================
# SETTINGS
# =============================================================================
elif _nav == "settings":
    st.markdown('<div class="page-header"><div class="page-title">Settings</div><div class="page-subtitle">Session management, database, and application configuration.</div></div>', unsafe_allow_html=True)
    _gs1, _gs2 = st.columns(2)
    with _gs1:
        sec_hdr("Session")
        st.markdown(f"""
<div class="glass-card">
  <div class="card-title">Current Session</div>
  <div class="p-row"><span class="p-key">Session ID</span>
    <code style="font-size:0.72rem;">{html.escape(st.session_state.get('sid',''))}</code></div>
  <div class="p-row"><span class="p-key">Nav section</span>
    <span class="p-cyan">{html.escape(st.session_state.get('nav',''))}</span></div>
</div>""", unsafe_allow_html=True)
        if st.button("↺  Reset Session State", key="reset_btn"):
            for _rk in ["last","plan","tok"]:
                st.session_state[_rk] = None
            st.session_state["cmd"] = ""
            db.log_activity(st.session_state["sid"],"Session state reset.","general","info")
            st.success("Session state cleared.")
            st.rerun()
    with _gs2:
        sec_hdr("Database", color="violet")
        st.markdown("""
<div class="glass-card">
  <div class="card-title card-title-v">SQLite Store</div>
  <div class="p-row"><span class="p-key">Location</span><span class="p-info">./sentientos.db</span></div>
  <div class="p-row"><span class="p-key">Tables</span><span class="p-ok">activity_log, tasks</span></div>
</div>""", unsafe_allow_html=True)
        if st.button("✕  Trim log (keep 200 entries)", key="settings_trim"):
            db.clear_old_logs(keep=200)
            db.log_activity(st.session_state["sid"],"Log trimmed from Settings.","general","info")
            st.success("Log trimmed.")
            st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)
    sec_hdr("About SentientOS")
    st.markdown("""
<div class="glass-card">
  <div class="card-title">SentientOS · v1.0 Prototype</div>
  <p style="font-size:0.82rem;color:#F5DABF;margin:0 0 14px;">
    An AI-native operating environment for goal-directed autonomous task execution.
    Goals are parsed by a rule-based planner, decomposed into verified steps, and executed
    through a sandboxed security gateway with cryptographic approval binding.
  </p>
  <div class="p-row"><span class="p-key">Planner</span><span class="p-info">Rule-based (no LLM required)</span></div>
  <div class="p-row"><span class="p-key">Security model</span><span class="p-ok">Sandbox + HMAC approval tickets</span></div>
  <div class="p-row"><span class="p-key">Shell execution</span><span class="p-warn">DISABLED</span></div>
  <div class="p-row"><span class="p-key">Network access</span><span class="p-warn">DISABLED</span></div>
  <div class="p-row"><span class="p-key">Code evaluation</span><span class="p-warn">DISABLED</span></div>
</div>""", unsafe_allow_html=True)

# GLOBAL BACK-TO-START BOTTOM BAR (visible on all sub-pages)
if _nav != "command_centre":
    st.markdown('<div style="height:32px;"></div>', unsafe_allow_html=True)
    _bot_col1, _bot_col2 = st.columns([2.5, 7.5])
    with _bot_col1:
        if st.button("←  Back to Start Page", key="global_bottom_back_btn", use_container_width=True):
            st.session_state["nav"] = "command_centre"
            st.rerun()
