//+------------------------------------------------------------------+
//|                                    20SMA_TrendSignals_Hybrid.mq5  |
//|        Trend-state engine - plot structure matched to original    |
//|        Buy/Sell trend lines + Dots + Candle coloring + Alerts     |
//+------------------------------------------------------------------+
#property copyright "Forex India Signal"
#property version   "2.00"
#property indicator_chart_window
#property indicator_buffers 10
#property indicator_plots   5

//--- Plot 1: Buy trend line (uptrend, below price)
#property indicator_label1  "Buy Trend Signal"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrDodgerBlue
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

//--- Plot 2: Sell trend line (downtrend, above price)
#property indicator_label2  "Sell Trend Signal"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrDarkOrange
#property indicator_style2  STYLE_SOLID
#property indicator_width2  1

//--- Plot 3: Buy dot
#property indicator_label3  "Buy Signal"
#property indicator_type3   DRAW_ARROW
#property indicator_color3  clrDodgerBlue
#property indicator_width3  1

//--- Plot 4: Sell dot
#property indicator_label4  "Sell Signal"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrDarkOrange
#property indicator_width4  1

//--- Plot 5: Colored candles (trend coloring)
#property indicator_label5  "Trend Candles"
#property indicator_type5   DRAW_COLOR_CANDLES
#property indicator_color5  clrDodgerBlue,clrDarkOrange,clrNONE
#property indicator_width5  1

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "= Signals ="
input bool            Signals_ON              = true;        // Signals_ON
input int             Signals_Period          = 2;           // Signals_Period
input ENUM_MA_METHOD  Signals_Method          = MODE_SMMA;   // Signals_Method
input int             Signals_Smoothing       = 0;           // Signals_Smoothing
input int             Signals_Shift           = 0;           // Signals_Shift
input double          Signals_Sell_Offset     = 0.0;         // Signals_Sell_Offset
input double          Signals_Buy_Offset      = 0.0;         // Signals_Buy_Offset
input int             Signals_Candle_Coloring = 500;         // Signals_Candle_Coloring
input bool            Confirm_On_Close        = true;        // ALERT only on candle CLOSE (visuals stay live)

input group "= Display ="
input bool            Show_Candles    = true;         // Color candles by trend
input bool            Show_TrendLines = true;         // Show trend lines
input bool            Show_CornerLabel = true;        // Price text in top-right corner
input bool            Show_DottedLine  = true;        // Dotted horizontal line at level
input bool            Strict_Trailing = true;         // Ratchet line (one-way lock, like original)

input group "= Alerts ="
input bool            EnableAlert     = true;         // Popup Alert
input bool            EnableMessage   = true;         // Chart Message
input bool            EnableSound     = true;         // Sound Alert
input string          SoundFile       = "alert.wav";  // Sound File

//--- Buffers
double BuyTrendLine[], SellTrendLine[];
double BuyBuffer[], SellBuffer[];
double CandleOpen[], CandleHigh[], CandleLow[], CandleClose[], CandleColor[];
double TrendBuffer[];   // calculation: +1 up / -1 down

//--- MA handles
int handleHigh = INVALID_HANDLE;
int handleLow  = INVALID_HANDLE;

datetime lastAlertTime = 0;
const string HLINE_NAME = "TSH_PriceLine";
const string LABEL_NAME = "TSH_CornerLabel";

//+------------------------------------------------------------------+
//| Init                                                              |
//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, BuyTrendLine,  INDICATOR_DATA);
   SetIndexBuffer(1, SellTrendLine, INDICATOR_DATA);
   SetIndexBuffer(2, BuyBuffer,     INDICATOR_DATA);
   SetIndexBuffer(3, SellBuffer,    INDICATOR_DATA);

   SetIndexBuffer(4, CandleOpen,    INDICATOR_DATA);
   SetIndexBuffer(5, CandleHigh,    INDICATOR_DATA);
   SetIndexBuffer(6, CandleLow,     INDICATOR_DATA);
   SetIndexBuffer(7, CandleClose,   INDICATOR_DATA);
   SetIndexBuffer(8, CandleColor,   INDICATOR_COLOR_INDEX);

   SetIndexBuffer(9, TrendBuffer,   INDICATOR_CALCULATIONS);

   PlotIndexSetInteger(2, PLOT_ARROW, 108);   // big dot
   PlotIndexSetInteger(3, PLOT_ARROW, 108);   // big dot

   for(int p = 0; p < 5; p++)
      PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   handleHigh = iMA(_Symbol, _Period, Signals_Period, Signals_Shift, Signals_Method, PRICE_HIGH);
   handleLow  = iMA(_Symbol, _Period, Signals_Period, Signals_Shift, Signals_Method, PRICE_LOW);

   if(handleHigh == INVALID_HANDLE || handleLow == INVALID_HANDLE)
   {
      Print("Failed to create MA handles");
      return(INIT_FAILED);
   }

   IndicatorSetString(INDICATOR_SHORTNAME,
      "20SMA TrendSignals Hybrid(" + IntegerToString(Signals_Period) + ")");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);

   lastAlertTime = 0;
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Optional extra smoothing                                          |
//+------------------------------------------------------------------+
void SmoothArray(double &arr[], int total, int smoothPeriod, int startFrom)
{
   if(smoothPeriod <= 1) return;
   static double tmp[];
   ArrayResize(tmp, total);
   for(int i = startFrom; i < total; i++)
   {
      double sum = 0;
      int cnt = 0;
      for(int j = 0; j < smoothPeriod && (i - j) >= 0; j++)
      {
         if(arr[i - j] == EMPTY_VALUE) break;
         sum += arr[i - j];
         cnt++;
      }
      tmp[i] = (cnt > 0) ? sum / cnt : arr[i];
   }
   for(int i = startFrom; i < total; i++)
      arr[i] = tmp[i];
}

//+------------------------------------------------------------------+
//| OnCalculate - incremental, restart-safe                           |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   if(!Signals_ON) return(rates_total);

   int minBars = Signals_Period + Signals_Smoothing + 2;
   if(rates_total < minBars) return(0);

   static double maHigh[], maLow[];
   if(CopyBuffer(handleHigh, 0, 0, rates_total, maHigh) < rates_total) return(0);
   if(CopyBuffer(handleLow,  0, 0, rates_total, maLow)  < rates_total) return(0);

   if(Signals_Smoothing > 0)
   {
      SmoothArray(maHigh, rates_total, Signals_Smoothing, minBars);
      SmoothArray(maLow,  rates_total, Signals_Smoothing, minBars);
   }

   double buyOff  = Signals_Buy_Offset  * _Point;
   double sellOff = Signals_Sell_Offset * _Point;

   int start = (prev_calculated == 0) ? minBars : prev_calculated - 1;

   if(prev_calculated == 0)
   {
      for(int i = 0; i < minBars; i++)
      {
         BuyTrendLine[i]  = EMPTY_VALUE;
         SellTrendLine[i] = EMPTY_VALUE;
         BuyBuffer[i]     = EMPTY_VALUE;
         SellBuffer[i]    = EMPTY_VALUE;
         CandleOpen[i]    = EMPTY_VALUE;
         CandleHigh[i]    = EMPTY_VALUE;
         CandleLow[i]     = EMPTY_VALUE;
         CandleClose[i]   = EMPTY_VALUE;
         CandleColor[i]   = 2;
         TrendBuffer[i]   = 0;
      }
   }

   //--- Main incremental loop
   for(int i = start; i < rates_total; i++)
   {
      BuyBuffer[i]     = EMPTY_VALUE;
      SellBuffer[i]    = EMPTY_VALUE;
      BuyTrendLine[i]  = EMPTY_VALUE;
      SellTrendLine[i] = EMPTY_VALUE;

      //--- 1) Trend state (restart-safe)
      //--- Visuals update LIVE like the original (candle color, line, dot).
      //--- Alerts are still confirmed on candle close (see Alerts section).
      double prevTrend = TrendBuffer[i - 1];
      double trend     = prevTrend;

      if(close[i] > maHigh[i - 1]) trend = 1;
      else if(close[i] < maLow[i - 1]) trend = -1;

      if(trend == 0) trend = (close[i] >= open[i]) ? 1 : -1;
      TrendBuffer[i] = trend;

      //--- 2) Trend lines + 3) Signal dot on flip
      if(trend > 0)
      {
         double lvl = maLow[i - 1] - buyOff;
         if(Strict_Trailing && prevTrend > 0 && BuyTrendLine[i - 1] != EMPTY_VALUE && lvl < BuyTrendLine[i - 1])
            lvl = BuyTrendLine[i - 1];

         if(Show_TrendLines)
            BuyTrendLine[i] = lvl;

         if(prevTrend < 0)
            BuyBuffer[i] = lvl;
      }
      else
      {
         double lvl = maHigh[i - 1] + sellOff;
         if(Strict_Trailing && prevTrend < 0 && SellTrendLine[i - 1] != EMPTY_VALUE && lvl > SellTrendLine[i - 1])
            lvl = SellTrendLine[i - 1];

         if(Show_TrendLines)
            SellTrendLine[i] = lvl;

         if(prevTrend > 0)
            SellBuffer[i] = lvl;
      }

      //--- 4) Candle coloring window
      bool inColorWindow = Show_Candles &&
                           ((Signals_Candle_Coloring <= 0) ||
                            (rates_total - i <= Signals_Candle_Coloring));
      if(inColorWindow)
      {
         CandleOpen[i]  = open[i];
         CandleHigh[i]  = high[i];
         CandleLow[i]   = low[i];
         CandleClose[i] = close[i];
         CandleColor[i] = (trend > 0) ? 0 : 1;
      }
      else
      {
         CandleOpen[i]  = EMPTY_VALUE;
         CandleHigh[i]  = EMPTY_VALUE;
         CandleLow[i]   = EMPTY_VALUE;
         CandleClose[i] = EMPTY_VALUE;
         CandleColor[i] = 2;
      }
   }

   //--- 5) Price display: corner label + dotted line
   int curr = rates_total - 1;
   if(curr >= 1)
   {
      double trendNow = TrendBuffer[curr];
      double lineLvl;
      if(trendNow > 0)
         lineLvl = (BuyTrendLine[curr] != EMPTY_VALUE) ? BuyTrendLine[curr]
                                                       : (maLow[curr - 1] - buyOff);
      else
         lineLvl = (SellTrendLine[curr] != EMPTY_VALUE) ? SellTrendLine[curr]
                                                        : (maHigh[curr - 1] + sellOff);
      color  lineClr  = (trendNow > 0) ? clrDodgerBlue : clrDarkOrange;
      string lblText  = (trendNow > 0) ? "BUY Line: " : "SELL Line: ";
      lblText += DoubleToString(lineLvl, _Digits);

      //--- Corner label (top-right, fixed position, always readable)
      if(Show_CornerLabel)
      {
         if(ObjectFind(0, LABEL_NAME) < 0)
         {
            ObjectCreate(0, LABEL_NAME, OBJ_LABEL, 0, 0, 0);
            ObjectSetInteger(0, LABEL_NAME, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
            ObjectSetInteger(0, LABEL_NAME, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
            ObjectSetInteger(0, LABEL_NAME, OBJPROP_XDISTANCE, 10);
            ObjectSetInteger(0, LABEL_NAME, OBJPROP_YDISTANCE, 25);
            ObjectSetString(0, LABEL_NAME, OBJPROP_FONT, "Arial Bold");
            ObjectSetInteger(0, LABEL_NAME, OBJPROP_FONTSIZE, 12);
            ObjectSetInteger(0, LABEL_NAME, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, LABEL_NAME, OBJPROP_HIDDEN, true);
         }
         ObjectSetString(0, LABEL_NAME, OBJPROP_TEXT, lblText);
         ObjectSetInteger(0, LABEL_NAME, OBJPROP_COLOR, lineClr);
      }
      else
         ObjectDelete(0, LABEL_NAME);

      //--- Dotted horizontal line (thin, doesn't cover candles)
      if(Show_DottedLine)
      {
         if(ObjectFind(0, HLINE_NAME) < 0)
         {
            ObjectCreate(0, HLINE_NAME, OBJ_HLINE, 0, 0, lineLvl);
            ObjectSetInteger(0, HLINE_NAME, OBJPROP_STYLE, STYLE_DOT);
            ObjectSetInteger(0, HLINE_NAME, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, HLINE_NAME, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, HLINE_NAME, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, HLINE_NAME, OBJPROP_BACK, true);
         }
         ObjectSetDouble(0, HLINE_NAME, OBJPROP_PRICE, lineLvl);
         ObjectSetInteger(0, HLINE_NAME, OBJPROP_COLOR, lineClr);
         ObjectSetString(0, HLINE_NAME, OBJPROP_TOOLTIP,
                         "Trend line level: " + DoubleToString(lineLvl, _Digits));
      }
      else
         ObjectDelete(0, HLINE_NAME);
   }

   //--- 6) Alerts (confirmed on closed candle when Confirm_On_Close)
   int sigBar = Confirm_On_Close ? rates_total - 2 : rates_total - 1;
   if(sigBar >= 1 && time[sigBar] != lastAlertTime)
   {
      string signalType = "";
      string details    = "";

      if(BuyBuffer[sigBar] != EMPTY_VALUE)
      {
         signalType = "BUY Signal";
         details = "Close: "       + DoubleToString(close[sigBar], _Digits) +
                   " > Prev SMA High: " + DoubleToString(maHigh[sigBar - 1], _Digits) +
                   "\nLine level: " + DoubleToString(maLow[sigBar - 1] - buyOff, _Digits);
      }
      else if(SellBuffer[sigBar] != EMPTY_VALUE)
      {
         signalType = "SELL Signal";
         details = "Close: "       + DoubleToString(close[sigBar], _Digits) +
                   " < Prev SMA Low: "  + DoubleToString(maLow[sigBar - 1], _Digits) +
                   "\nLine level: " + DoubleToString(maHigh[sigBar - 1] + sellOff, _Digits);
      }

      if(signalType != "")
      {
         lastAlertTime = time[sigBar];

         if(EnableAlert)
            Alert(signalType, " on ", _Symbol, " (", EnumToString(Period()), ")\n", details);

         if(EnableMessage)
            Comment(signalType, " Generated!\n",
                    "Symbol: ", _Symbol, "\n",
                    "Timeframe: ", EnumToString(Period()), "\n",
                    details, "\n",
                    "Time: ", TimeToString(time[sigBar]));

         if(EnableSound)
            PlaySound(SoundFile);
      }
   }

   return(rates_total);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Comment("");
   ObjectDelete(0, HLINE_NAME);
   ObjectDelete(0, LABEL_NAME);
   if(handleHigh != INVALID_HANDLE) IndicatorRelease(handleHigh);
   if(handleLow  != INVALID_HANDLE) IndicatorRelease(handleLow);
}
//+------------------------------------------------------------------+
