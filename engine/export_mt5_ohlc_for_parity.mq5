//+------------------------------------------------------------------+
//|                              export_mt5_ohlc_for_parity.mq5      |
//| Root-cause helper — dumps the LIVE MT5 candle data (Open/High/    |
//| Low/Close) for M15 (last N bars) to CSV, so it can be diffed      |
//| against data/merged/ohlc_merged.csv (Python source) to check if   |
//| the ADX-parity mismatch is a data-source problem, not a formula   |
//| problem.                                                          |
//|                                                                    |
//| Run as a Script — attach to any M15 chart, no inputs to get wrong.|
//+------------------------------------------------------------------+
#property script_show_inputs

input int      Bars_To_Export = 200;
input string   Out_File = "ohlc_mt5_export.csv";   // written to MQL5\Files\

void OnStart()
{
   string sym = _Symbol;
   Print("Using symbol: ", sym);

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(sym, PERIOD_M15, 1, Bars_To_Export, rates);   // shift=1: skip forming bar

   if(copied <= 0)
   {
      Print("CopyRates failed, error ", GetLastError());
      return;
   }
   Print("Copied ", copied, " M15 bars");

   int fh = FileOpen(Out_File, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
   if(fh == INVALID_HANDLE)
   {
      Print("Failed to open output file: ", Out_File, " error ", GetLastError());
      return;
   }
   FileWrite(fh, "bar_close_time", "open", "high", "low", "close");

   for(int i = 0; i < copied; i++)
   {
      string bar_close_str = TimeToString(rates[i].time + PeriodSeconds(PERIOD_M15), TIME_DATE|TIME_SECONDS);
      FileWrite(fh, bar_close_str,
                DoubleToString(rates[i].open, 2),
                DoubleToString(rates[i].high, 2),
                DoubleToString(rates[i].low, 2),
                DoubleToString(rates[i].close, 2));
   }

   FileClose(fh);
   Print("DONE — file written to MQL5\\Files\\", Out_File);
}
