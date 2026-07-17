//+------------------------------------------------------------------+
//|                              export_mt5_adx_for_parity.mq5       |
//| Test 1 (MT5 parity) helper — dumps the LIVE MT5 iADX() buffer    |
//| values for M15/M30/H1/H4 to CSV, for diffing against the Python  |
//| EMA ADX computation (export_python_adx_for_mt5_parity.py).       |
//|                                                                   |
//| Run as a Script (not an EA/indicator) — attach to any chart of   |
//| the symbol you trade (e.g. XAUUSD), it reads params below.       |
//+------------------------------------------------------------------+
#property script_show_inputs

input string   Symbol_ = "XAUUSD";
input int      ADX_Period = 14;
input int      Bars_To_Export = 200;
input string   Out_File = "adx_mt5_export.csv";   // written to MQL5\Files\

void OnStart()
{
   ENUM_TIMEFRAMES tfs[4] = {PERIOD_M15, PERIOD_M30, PERIOD_H1, PERIOD_H4};
   string tf_names[4] = {"M15", "M30", "H1", "H4"};

   int fh = FileOpen(Out_File, FILE_WRITE|FILE_CSV|FILE_ANSI);
   if(fh == INVALID_HANDLE)
   {
      Print("Failed to open output file: ", Out_File, " error ", GetLastError());
      return;
   }
   FileWrite(fh, "timeframe", "bar_close_time", "mt5_adx", "mt5_plus_di", "mt5_minus_di");

   for(int t = 0; t < 4; t++)
   {
      int handle = iADX(Symbol_, tfs[t], ADX_Period);
      if(handle == INVALID_HANDLE)
      {
         Print("Failed to create iADX handle for ", tf_names[t], " error ", GetLastError());
         continue;
      }

      double adx_buf[], plus_di_buf[], minus_di_buf[];
      ArraySetAsSeries(adx_buf, true);
      ArraySetAsSeries(plus_di_buf, true);
      ArraySetAsSeries(minus_di_buf, true);

      // buffer 0 = ADX main, 1 = +DI, 2 = -DI (standard iADX buffer layout)
      int copied_adx = CopyBuffer(handle, 0, 1, Bars_To_Export, adx_buf);   // shift=1: skip forming bar
      int copied_pdi = CopyBuffer(handle, 1, 1, Bars_To_Export, plus_di_buf);
      int copied_ndi = CopyBuffer(handle, 2, 1, Bars_To_Export, minus_di_buf);

      if(copied_adx <= 0)
      {
         Print("CopyBuffer failed for ", tf_names[t], " error ", GetLastError());
         IndicatorRelease(handle);
         continue;
      }

      for(int i = 0; i < copied_adx; i++)
      {
         datetime bar_time = iTime(Symbol_, tfs[t], i + 1);   // matches shift=1 above (last CLOSED bar)
         string bar_close_str = TimeToString(bar_time + PeriodSeconds(tfs[t]), TIME_DATE|TIME_SECONDS);
         FileWrite(fh, tf_names[t], bar_close_str,
                   DoubleToString(adx_buf[i], 4),
                   DoubleToString(plus_di_buf[i], 4),
                   DoubleToString(minus_di_buf[i], 4));
      }

      IndicatorRelease(handle);
      Print("Exported ", copied_adx, " bars for ", tf_names[t]);
   }

   FileClose(fh);
   Print("DONE — file written to MQL5\\Files\\", Out_File);
   Print("Copy this file next to adx_python_export.csv and run compare_adx_parity.py");
}
