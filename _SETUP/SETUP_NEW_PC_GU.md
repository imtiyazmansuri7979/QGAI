# QGAI v2 — નવા PC પર setup (ગુજરાતી, ટૂંકમાં)

આ `_SETUP` folder + આખું `QGAI` folder નવા PC પર copy કરી, નીચેના steps કરો.

---

## Steps

**1. Python install કરો** (એક વાર)
- https://www.python.org/downloads/ → **Python 3.12** download.
- Install વખતे **"Add Python to PATH"** ✅ tick કરો (બહુ important).

**2. MetaTrader5 terminal install કરો**
- તમારા broker (Vantage વગેરે) નું MT5 install + login કરો.

**3. QGAI folder copy કરો** — આખું `C:\QGAI` → નવા PC પર `C:\QGAI`.
   **MUST copy:** `engine\` (.py code) · `data\models\final\` (.pkl models) · `data\merged\` (.csv) ·
   `data\` ના news+trades files · `Start\` · `_SETUP\`.
   **Copy ન કરો:** `engine\config_mt5.py` (credentials — નવી બનાવો) · `logs\` (auto) · `__pycache__\`.
   **Optional:** `backtest\` · `docs\`.
   > સહેલું: આખું folder copy કરો, પછી નવા PC પર `config_mt5.py` નવી બનાવો + `logs\` delete કરો.

**4. Dependencies install કરો** ⭐
- `C:\QGAI\_SETUP\INSTALL_QGAI.bat` પર **double-click**.
- એ Python શોધી, બધા packages (xgboost, MetaTrader5, pandas...) install કરી, verify કરશे.
- "INSTALL COMPLETE" દેખાય = થઈ ગયું.

**5. Credentials file બનાવો**
- `C:\QGAI\engine\config_mt5_template.py` ને copy કરી **`C:\QGAI\engine\config_mt5.py`** નામ આપો.
- એમાં તમારા **login / password / server / symbol** ભરો.
- ⚠️ આ file માં real password છે — કોઈને આપવી નહીં, git પર નહીं.

**6. ચલાવો** (પહેલા **DEMO** પર!)
- `C:\QGAI\Start\1_Start_Trading.bat` → live trading શરૂ.
- `C:\QGAI\Start\5_Dashboard.bat` → dashboard.

---

## Checklist (નવા PC પર બધું છે?)
- [ ] Python 3.12 (PATH સાથे)
- [ ] MT5 terminal + login
- [ ] `C:\QGAI` folder (data + models + engine + Start)
- [ ] `INSTALL_QGAI.bat` ચાલ્યો ("All core packages import fine")
- [ ] `config_mt5.py` બનાવ્યો (credentials સાથે)
- [ ] DEMO પર test

---

## વાંધો આવે તો
- **"Python not found"** → Python install કરો + "Add to PATH" tick, ફરી bat ચલાવો.
- **package install fail** → internet check કરો, bat ફરી ચલાવો.
- **MT5 connect fail** → MT5 terminal ખુલ્લું છે + login છે + config_mt5.py બરાબર છે એ check કરો.

> વધુ માહિતી: `C:\QGAI\docs\USER_GUIDE_GU.md` (system logic) · `docs\QGAI_GUIDE.md` (master).
