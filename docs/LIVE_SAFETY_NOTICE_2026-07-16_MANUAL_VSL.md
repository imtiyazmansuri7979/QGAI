# LIVE SAFETY NOTICE - 2026-07-16 - Manual vSL Enforcement

## Issue
Manual BUY trade showed a dashboard virtual stop loss (`vSL`) but the system did not close when price briefly moved below that vSL.

Observed live case:

- Manual BUY entry: `4041.43`
- Dashboard vSL: `4022.08`
- Bridge heartbeat showed price: `4016.61` at `2026-07-16 17:46:52`
- Expected: manual position closes because BUY price was below vSL
- Actual: no `COMBINED vSL hit` close log appeared

## Root Cause
`engine/bridge_manual.py` enforced manual vSL only inside the fresh ratchet-line branch:

- If ratchet line was available, it calculated/enforced vSL.
- If ratchet line was unavailable on that tick, old dashboard vSL remained visible but was not enforced.

So the displayed vSL was not guaranteed to remain active on every tick.

## Fix
Changed `engine/bridge_manual.py` so the last ratcheted vSL is always enforced before trying to calculate a fresh ratchet line.

New behavior:

- If previous vSL exists, close manual position when breached.
- This works even when current ratchet-line read fails.
- Fresh line can still ratchet vSL higher/lower after that check.

## Follow-up Finding During Live Recheck
After the bridge restart, the manual trade's in-memory vSL reset from the ratcheted `4022.08` back to the wide floor `3920.19`.

That exposed a second safety gap:

- Manual vSL state was not persisted across bridge restarts.
- A restart could temporarily forget the tighter ratcheted manual vSL.

Follow-up fix added:

- `engine/logs/manual_vsl_state.json` persistence for manual vSL state.
- Restart recovery from that state file.
- Last-resort recovery from `bridge.log` for existing live incidents where no state file existed yet.

Live recheck result:

- `2026-07-16 18:00:06`: system closed the manual BUY at previous vSL `4022.08`.
- Direct MT5 check after close: primary and both slave accounts had `0` open positions.

Also changed `engine/bridge_main.py` so manual manager exceptions are logged with stack traces instead of silently ignored.

## Files Changed
- `engine/bridge_manual.py`
- `engine/bridge_main.py`
- Documentation:
  - `docs/LIVE_SAFETY_NOTICE_2026-07-16_MANUAL_VSL.md`
  - `docs/FIXES_CHANGELOG4.md`
  - `docs/BUG_LOG.md`
  - `docs/TASKS.md`

## Verification
- `python -m py_compile engine/bridge_manual.py engine/bridge_main.py` passed.
- Live MT5 diagnostic after fix showed current price above vSL, so no immediate close was expected at that moment:
  - Bid around `4028.97`
  - vSL `4022.08`

## Required Operator Action
Restart the live bridge to load this code change.

Until restart, the currently running `bridge_main.py` process still uses the old in-memory code.

## Gujarati Summary
Manual trade માટે dashboardમાં vSL દેખાતું હતું, પણ જો તે tick પર ratchet line ના મળે તો જૂનું vSL enforce થતું નહોતું. એટલે price vSL નીચે ગયું છતાં close ન થયું. હવે જૂનું/last vSL હંમેશા enforce થશે. Bridge restart કરવો જરૂરી છે.
