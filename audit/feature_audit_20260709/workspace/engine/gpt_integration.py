"""
gpt_integration.py — ChatGPT Integration for QGAI
──────────────────────────────────────────────────

Comprehensive OpenAI ChatGPT integration for:
  1. News Analysis — interpret economic news for trade filtering
  2. Trade Commentary — real-time analysis of open trades
  3. Signal Validation — double-check model BUY/SELL decisions
  4. Dashboard Insights — market analysis for the dashboard
  5. Strategy Review — analyze backtest results
  6. Custom Reporting — generate daily/weekly AI reports

Usage:
    from gpt_integration import GPTAnalyzer
    gpt = GPTAnalyzer()
    
    # News analysis
    analysis = gpt.analyze_news("USD jobs report beat expectations")
    
    # Trade commentary
    comment = gpt.analyze_trade(price=2500.50, signal="BUY", win_prob=0.72)
    
    # Signal validation
    validation = gpt.validate_signal(signal="SELL", market_context="trending down")
    
    # Report generation
    report = gpt.generate_trade_report(trades_data, date_range=(start, end))
"""

import os
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
import logging

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️  OpenAI library not installed. Run: pip install openai")

# ────────────────────────────────────────────────────────────────
# Logger setup
# ────────────────────────────────────────────────────────────────
logger = logging.getLogger("gpt_integration")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class GPTAnalyzer:
    """
    Main ChatGPT analysis engine for QGAI.
    Requires OPENAI_API_KEY environment variable or config.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize GPT analyzer.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: GPT model to use (gpt-4o-mini, gpt-4, gpt-3.5-turbo, etc.)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library required. Run: pip install openai")
        
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. Set it via:\n"
                "  1. Environment variable: set OPENAI_API_KEY=sk-...\n"
                "  2. Or pass api_key parameter to GPTAnalyzer()"
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.request_count = 0
        self.token_count = 0
        logger.info(f"GPT Analyzer initialized with model: {self.model}")

    # ────────────────────────────────────────────────────────────────
    # 1. NEWS ANALYSIS
    # ────────────────────────────────────────────────────────────────

    def analyze_news(
        self, 
        news_headline: str, 
        news_context: Optional[str] = None,
        current_price: Optional[float] = None,
        market_regime: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze economic news and its potential impact on XAUUSD.
        
        Args:
            news_headline: News title/headline
            news_context: Optional full news text
            current_price: Current gold price (for context)
            market_regime: Current market regime (Trending/Ranging/Volatile)
        
        Returns:
            {
                "sentiment": "bullish|bearish|neutral",
                "impact_on_gold": "positive|negative|neutral",
                "intensity": 1-10,
                "reasoning": "...",
                "trade_action": "BUY_BIAS|SELL_BIAS|NEUTRAL|AVOID",
                "confidence": 0.0-1.0
            }
        """
        context_str = ""
        if current_price:
            context_str += f"\nCurrent Gold Price: ${current_price:.2f}"
        if market_regime:
            context_str += f"\nMarket Regime: {market_regime}"
        if news_context:
            context_str += f"\n\nFull News Text:\n{news_context}"

        prompt = f"""
You are a financial analyst specializing in gold (XAUUSD) trading.
Analyze the following economic news and assess its potential impact on gold prices.

News Headline: {news_headline}{context_str}

Provide your analysis in JSON format with these fields:
- sentiment: "bullish", "bearish", or "neutral" (for USD generally)
- impact_on_gold: "positive" (gold up), "negative" (gold down), or "neutral"
- intensity: 1-10 scale of how strong the impact could be
- reasoning: 2-3 sentence explanation of why
- trade_action: "BUY_BIAS", "SELL_BIAS", "NEUTRAL", or "AVOID"
- confidence: 0.0-1.0 confidence in your assessment

Response ONLY with valid JSON, no markdown.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300
            )
            self.request_count += 1
            
            text = response.choices[0].message.content.strip()
            # Remove markdown code blocks if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            result = json.loads(text)
            logger.info(f"News analysis: {result.get('trade_action', 'N/A')}")
            return result
        except Exception as e:
            logger.error(f"News analysis failed: {e}")
            return {
                "sentiment": "neutral",
                "impact_on_gold": "neutral",
                "intensity": 0,
                "reasoning": f"Analysis failed: {str(e)}",
                "trade_action": "NEUTRAL",
                "confidence": 0.0
            }

    # ────────────────────────────────────────────────────────────────
    # 2. TRADE COMMENTARY
    # ────────────────────────────────────────────────────────────────

    def analyze_trade(
        self,
        price: float,
        signal: str,  # "BUY" or "SELL"
        win_probability: float,
        market_regime: Optional[str] = None,
        atr_pct: Optional[float] = None,
        volume_spike: Optional[bool] = None,
        recent_momentum: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate real-time commentary on an active trade.
        
        Args:
            price: Current gold price
            signal: "BUY" or "SELL"
            win_probability: Model's win probability (0.0-1.0)
            market_regime: Current regime
            atr_pct: ATR as % of price
            volume_spike: Was there a volume spike?
            recent_momentum: Trend direction
        
        Returns:
            {
                "setup_quality": "strong|solid|moderate|weak",
                "commentary": "...",
                "risk_level": "low|medium|high",
                "key_levels": "...",
                "next_catalyst": "..."
            }
        """
        details = f"Price: ${price:.2f}, Signal: {signal}, Win Prob: {win_probability*100:.1f}%"
        if market_regime:
            details += f", Regime: {market_regime}"
        if atr_pct:
            details += f", ATR: {atr_pct:.3f}%"
        if recent_momentum:
            details += f", Momentum: {recent_momentum}"

        prompt = f"""
You are a professional gold trader analyzing a new trading setup.

{details}

Provide a brief, actionable trade commentary in JSON format:
- setup_quality: "strong", "solid", "moderate", or "weak"
- commentary: 1-2 sentences on the setup quality and why
- risk_level: "low", "medium", or "high"
- key_levels: Expected support/resistance (mention typical levels for gold)
- next_catalyst: What event/price level could change the trade outcome?

Response ONLY with valid JSON, no markdown.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=250
            )
            self.request_count += 1
            
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            result = json.loads(text)
            logger.info(f"Trade analysis: {result.get('setup_quality', 'N/A')}")
            return result
        except Exception as e:
            logger.error(f"Trade analysis failed: {e}")
            return {
                "setup_quality": "unknown",
                "commentary": f"Analysis unavailable: {str(e)}",
                "risk_level": "medium",
                "key_levels": "N/A",
                "next_catalyst": "N/A"
            }

    # ────────────────────────────────────────────────────────────────
    # 3. SIGNAL VALIDATION
    # ────────────────────────────────────────────────────────────────

    def validate_signal(
        self,
        signal: str,  # "BUY" or "SELL"
        win_probability: float,
        market_context: Optional[str] = None,
        price_action: Optional[str] = None,
        other_signals: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Use GPT to validate/question the model's signal decision.
        
        Args:
            signal: The model's signal
            win_probability: Model's confidence
            market_context: Description of current market (e.g., "trending down")
            price_action: Recent price patterns
            other_signals: Other technical signals
        
        Returns:
            {
                "agrees": True/False,
                "confidence": 0.0-1.0,
                "reasoning": "...",
                "concerns": ["...", "..."],
                "alternative_view": "...",
                "override_recommendation": "TRUST_MODEL|QUESTION|OVERRIDE"
            }
        """
        details = f"Model Signal: {signal}, Win Prob: {win_probability*100:.1f}%"
        if market_context:
            details += f"\nMarket Context: {market_context}"
        if price_action:
            details += f"\nPrice Action: {price_action}"
        if other_signals:
            details += f"\nOther Signals: {other_signals}"

        prompt = f"""
You are a skeptical trading review agent. The model has generated this signal:

{details}

Based on the context, do you agree with the signal? Provide a critical review in JSON:
- agrees: true/false (do you agree with the signal?)
- confidence: 0.0-1.0 (how confident are you in your assessment?)
- reasoning: 1-2 sentences explaining your position
- concerns: list of 0-3 concerns (potential issues with the signal)
- alternative_view: What's the opposite perspective?
- override_recommendation: "TRUST_MODEL", "QUESTION", or "OVERRIDE"

Response ONLY with valid JSON, no markdown.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300
            )
            self.request_count += 1
            
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            result = json.loads(text)
            logger.info(f"Signal validation: {result.get('override_recommendation', 'N/A')}")
            return result
        except Exception as e:
            logger.error(f"Signal validation failed: {e}")
            return {
                "agrees": True,
                "confidence": 0.0,
                "reasoning": f"Validation unavailable: {str(e)}",
                "concerns": [],
                "alternative_view": "N/A",
                "override_recommendation": "TRUST_MODEL"
            }

    # ────────────────────────────────────────────────────────────────
    # 4. DASHBOARD INSIGHTS
    # ────────────────────────────────────────────────────────────────

    def generate_dashboard_insight(
        self,
        current_price: float,
        price_change_1h: float,
        price_change_24h: float,
        open_trades: int,
        daily_pnl: float,
        regime: str,
        win_rate: Optional[float] = None
    ) -> Dict[str, str]:
        """
        Generate brief, non-technical insights for the dashboard.
        
        Returns:
            {
                "market_summary": "...",
                "performance_note": "...",
                "action_prompt": "..."
            }
        """
        prompt = f"""
Provide a brief, concise dashboard summary (1-2 sentences each) as JSON:
Current Price: ${current_price:.2f}
1H Change: {price_change_1h:+.2f}%
24H Change: {price_change_24h:+.2f}%
Open Trades: {open_trades}
Daily P&L: ${daily_pnl:+.2f}
Market Regime: {regime}
{f'Win Rate: {win_rate*100:.1f}%' if win_rate else ''}

Provide JSON with:
- market_summary: Current market state in 1 sentence
- performance_note: How is the system performing today?
- action_prompt: What should the trader consider?

Response ONLY with valid JSON, no markdown.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=200
            )
            self.request_count += 1
            
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            result = json.loads(text)
            return result
        except Exception as e:
            logger.error(f"Dashboard insight failed: {e}")
            return {
                "market_summary": "Market analysis unavailable",
                "performance_note": "Check system status",
                "action_prompt": "Review recent signals"
            }

    # ────────────────────────────────────────────────────────────────
    # 5. STRATEGY REVIEW / BACKTEST ANALYSIS
    # ────────────────────────────────────────────────────────────────

    def analyze_backtest_results(
        self,
        results_dict: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Analyze backtest results and suggest improvements.
        
        Args:
            results_dict: Dictionary with keys like:
                - total_trades
                - win_rate
                - profit_factor
                - max_drawdown
                - sharpe_ratio
                - period (date range)
        
        Returns:
            {
                "performance_assessment": "...",
                "strengths": "...",
                "weaknesses": "...",
                "improvement_suggestions": "...",
                "risk_assessment": "..."
            }
        """
        results_str = json.dumps(results_dict, indent=2)
        prompt = f"""
You are a quant strategy analyst. Review these backtest results and provide insights:

{results_str}

Provide analysis in JSON:
- performance_assessment: Is this good performance? 1-2 sentences.
- strengths: What's working well? (e.g., risk management, win rate)
- weaknesses: What needs improvement? (e.g., drawdown, scalability)
- improvement_suggestions: 2-3 specific ideas to boost performance
- risk_assessment: How robust is this strategy? Will it survive live trading?

Response ONLY with valid JSON, no markdown.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=400
            )
            self.request_count += 1
            
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            result = json.loads(text)
            logger.info("Backtest analysis complete")
            return result
        except Exception as e:
            logger.error(f"Backtest analysis failed: {e}")
            return {
                "performance_assessment": "Analysis unavailable",
                "strengths": "N/A",
                "weaknesses": "N/A",
                "improvement_suggestions": "N/A",
                "risk_assessment": "N/A"
            }

    # ────────────────────────────────────────────────────────────────
    # 6. CUSTOM REPORTING
    # ────────────────────────────────────────────────────────────────

    def generate_trade_report(
        self,
        trades: List[Dict[str, Any]],
        date_range_start: Optional[str] = None,
        date_range_end: Optional[str] = None,
        include_recommendations: bool = True
    ) -> str:
        """
        Generate a formatted daily/weekly trade report.
        
        Args:
            trades: List of trade dicts (entry_time, exit_time, pnl, reason, etc.)
            date_range_start: Start date for report
            date_range_end: End date for report
            include_recommendations: Add forward-looking recommendations?
        
        Returns:
            Formatted report as string (markdown)
        """
        # Summarize trades for the prompt
        trade_summary = self._summarize_trades(trades)
        
        report_type = "Weekly" if len(trades) > 5 else "Daily"
        date_info = ""
        if date_range_start and date_range_end:
            date_info = f" ({date_range_start} to {date_range_end})"
        
        prompt = f"""
Generate a professional {report_type} Trading Report{date_info} in markdown format.

Trade Summary:
{trade_summary}

Include sections:
1. Executive Summary (2-3 sentences: how did the strategy perform?)
2. Trade Analysis (top winners/losers, avg win size, holding times)
3. Market Conditions (what was the dominant market regime?)
4. Risk Management (were stops effective? any near-calls?)
5. Key Insights (patterns observed, lessons learned)
{'6. Recommendations (forward-looking advice for next period)' if include_recommendations else ''}

Use markdown formatting. Be concise and actionable.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=800
            )
            self.request_count += 1
            
            report = response.choices[0].message.content
            logger.info(f"Generated {report_type} report ({len(trades)} trades)")
            return report
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return f"Report generation failed: {str(e)}"

    def _summarize_trades(self, trades: List[Dict[str, Any]]) -> str:
        """Helper to create a concise summary of trades for the prompt."""
        if not trades:
            return "No trades in this period."
        
        total_trades = len(trades)
        winners = [t for t in trades if t.get("pnl", 0) > 0]
        losers = [t for t in trades if t.get("pnl", 0) < 0]
        win_rate = len(winners) / total_trades if total_trades > 0 else 0
        
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        avg_win = sum(t.get("pnl", 0) for t in winners) / len(winners) if winners else 0
        avg_loss = sum(abs(t.get("pnl", 0)) for t in losers) / len(losers) if losers else 0
        
        summary = f"""
Total Trades: {total_trades}
Winners: {len(winners)} ({win_rate*100:.1f}%)
Losers: {len(losers)} ({(1-win_rate)*100:.1f}%)
Total P&L: ${total_pnl:.2f}
Avg Win: ${avg_win:.2f}
Avg Loss: ${avg_loss:.2f}
Profit Factor: {(sum(t.get('pnl', 0) for t in winners) / sum(abs(t.get('pnl', 0)) for t in losers) if losers else 0):.2f}
"""
        return summary

    # ────────────────────────────────────────────────────────────────
    # Utility: Stats & Token Usage
    # ────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, int]:
        """Get usage statistics."""
        return {
            "requests": self.request_count,
            "estimated_tokens": self.token_count
        }

    def reset_stats(self):
        """Reset usage counters."""
        self.request_count = 0
        self.token_count = 0


# ────────────────────────────────────────────────────────────────
# Convenience function for quick initialization
# ────────────────────────────────────────────────────────────────

def get_gpt_analyzer(
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> Optional[GPTAnalyzer]:
    """
    Quick initialization with error handling.
    
    Returns:
        GPTAnalyzer instance, or None if OpenAI is not available/configured.
    """
    try:
        return GPTAnalyzer(api_key=api_key, model=model)
    except (ImportError, ValueError) as e:
        logger.warning(f"GPT not available: {e}")
        return None


if __name__ == "__main__":
    # Quick test
    print("Testing GPT Integration...")
    
    try:
        gpt = GPTAnalyzer()
        
        # Test news analysis
        news_result = gpt.analyze_news(
            "Fed raises interest rates by 50 bps",
            current_price=2450.50,
            market_regime="Trending"
        )
        print("\n1. News Analysis:")
        print(json.dumps(news_result, indent=2))
        
        # Test signal validation
        validation = gpt.validate_signal(
            signal="BUY",
            win_probability=0.72,
            market_context="Gold trending up on risk-off sentiment"
        )
        print("\n2. Signal Validation:")
        print(json.dumps(validation, indent=2))
        
        # Test dashboard insight
        insight = gpt.generate_dashboard_insight(
            current_price=2450.50,
            price_change_1h=0.25,
            price_change_24h=1.20,
            open_trades=1,
            daily_pnl=125.50,
            regime="Trending",
            win_rate=0.68
        )
        print("\n3. Dashboard Insight:")
        print(json.dumps(insight, indent=2))
        
        print(f"\n✓ GPT Integration working! Used {gpt.request_count} API requests")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        print("  Make sure OPENAI_API_KEY is set!")
