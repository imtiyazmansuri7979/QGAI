"""
gpt_backtest_analyzer.py — Backtest Analysis with ChatGPT
──────────────────────────────────────────────────────────

Analyzes backtest results using ChatGPT for insights on strategy performance,
drawdowns, win rates, and improvement suggestions.

Usage:
    from gpt_backtest_analyzer import BacktestAnalyzer
    
    analyzer = BacktestAnalyzer()
    
    # Load backtest results
    results = analyzer.load_backtest_results("backtest/results/final_backtest.txt")
    
    # Analyze with GPT
    analysis = analyzer.analyze_results(results)
    print(analysis)
    
    # Generate improvement suggestions
    suggestions = analyzer.get_improvement_suggestions(results)
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
import logging
import re

from gpt_integration import GPTAnalyzer, get_gpt_analyzer

logger = logging.getLogger("backtest_analyzer")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class BacktestAnalyzer:
    """Analyze backtest results with ChatGPT insights."""

    def __init__(self, gpt_analyzer: Optional[GPTAnalyzer] = None):
        """Initialize with optional GPT analyzer."""
        self.gpt = gpt_analyzer or get_gpt_analyzer()
        if not self.gpt:
            logger.warning("GPT not available — limited analysis available")

    def load_backtest_results(self, filepath: str) -> Dict[str, Any]:
        """
        Load backtest results from a file.
        
        Supports:
        - JSON files
        - CSV files (expects headers in first row)
        - Plain text files with key:value pairs
        
        Args:
            filepath: Path to backtest results file
        
        Returns:
            Dict with parsed results
        """
        try:
            p = Path(filepath)
            if not p.exists():
                logger.error(f"File not found: {filepath}")
                return {}
            
            if p.suffix == ".json":
                with open(p) as f:
                    return json.load(f)
            
            elif p.suffix == ".csv":
                df = pd.read_csv(p)
                return df.to_dict('list')
            
            else:  # Plain text
                results = {}
                with open(p) as f:
                    for line in f:
                        line = line.strip()
                        if ':' in line and not line.startswith('#'):
                            key, value = line.split(':', 1)
                            key = key.strip().lower()
                            value = value.strip()
                            # Try to convert to number
                            try:
                                if '.' in value:
                                    results[key] = float(value)
                                else:
                                    results[key] = int(value)
                            except:
                                results[key] = value
                return results
        
        except Exception as e:
            logger.error(f"Failed to load backtest file: {e}")
            return {}

    def extract_key_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key trading metrics from results.
        
        Returns standardized dict with:
            - total_trades
            - win_rate
            - profit_factor
            - max_drawdown
            - sharpe_ratio
            - total_pnl
            - etc.
        """
        metrics = {}
        
        # Flexible key matching (case-insensitive)
        key_map = {
            'total_trades': ['total_trades', 'trades', 'num_trades', 'trade_count'],
            'win_rate': ['win_rate', 'win%', 'winrate', 'pct_profitable'],
            'profit_factor': ['profit_factor', 'profitfactor', 'pf'],
            'max_drawdown': ['max_drawdown', 'maxdd', 'max_dd', 'drawdown'],
            'sharpe_ratio': ['sharpe_ratio', 'sharpe', 'sharpe_ratio'],
            'total_pnl': ['total_pnl', 'pnl', 'net_profit', 'total_profit'],
            'avg_win': ['avg_win', 'average_win', 'avg_profit'],
            'avg_loss': ['avg_loss', 'average_loss', 'avg_loss'],
            'consecutive_losses': ['consecutive_losses', 'max_losses', 'consec_losses'],
            'recovery_factor': ['recovery_factor', 'recovery'],
        }
        
        results_lower = {k.lower(): v for k, v in results.items()}
        
        for standard_key, alt_keys in key_map.items():
            for alt_key in alt_keys:
                if alt_key in results_lower:
                    metrics[standard_key] = results_lower[alt_key]
                    break
        
        return metrics

    def analyze_results(self, results: Dict[str, Any]) -> Dict[str, str]:
        """
        Use GPT to analyze backtest results.
        
        Args:
            results: Backtest results dict
        
        Returns:
            Analysis dict with insights
        """
        if not self.gpt:
            return {"analysis": "GPT not available"}
        
        metrics = self.extract_key_metrics(results)
        
        try:
            analysis = self.gpt.analyze_backtest_results(metrics)
            logger.info("Backtest analysis complete")
            return analysis
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {"analysis": f"Analysis failed: {str(e)}"}

    def get_improvement_suggestions(
        self,
        results: Dict[str, Any],
        focus_area: Optional[str] = None
    ) -> List[str]:
        """
        Generate specific improvement suggestions.
        
        Args:
            results: Backtest results
            focus_area: "drawdown", "winrate", "profitability", or None for general
        
        Returns:
            List of actionable suggestions
        """
        if not self.gpt:
            return ["GPT not available for suggestions"]
        
        metrics = self.extract_key_metrics(results)
        
        prompt = f"""
Given these backtest metrics:
{json.dumps(metrics, indent=2)}

Focus area: {focus_area or 'Overall performance'}

Generate 3-5 specific, actionable improvements. Be concrete (e.g., "increase stop-loss 
distance" not "optimize risk management"). Return as a JSON list of strings.

Example format: ["Increase profit target from 1% to 2%", "Reduce entry filter..."]

RESPOND ONLY WITH VALID JSON LIST, NO MARKDOWN OR EXPLANATION.
"""
        
        try:
            response = self.gpt.client.chat.completions.create(
                model=self.gpt.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300
            )
            
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            suggestions = json.loads(text)
            logger.info(f"Generated {len(suggestions)} improvement suggestions")
            return suggestions
        
        except Exception as e:
            logger.error(f"Failed to generate suggestions: {e}")
            return [f"Error: {str(e)}"]

    def compare_backtests(
        self,
        baseline_results: Dict[str, Any],
        new_results: Dict[str, Any],
        baseline_name: str = "Baseline",
        new_name: str = "New"
    ) -> Dict[str, str]:
        """
        Compare two backtest runs.
        
        Returns:
            {
                "summary": "...",
                "improvements": ["...", "..."],
                "regressions": ["...", "..."],
                "verdict": "Better|Worse|Similar"
            }
        """
        if not self.gpt:
            return {"summary": "GPT not available"}
        
        baseline_metrics = self.extract_key_metrics(baseline_results)
        new_metrics = self.extract_key_metrics(new_results)
        
        prompt = f"""
Compare two backtest runs:

{baseline_name}:
{json.dumps(baseline_metrics, indent=2)}

{new_name}:
{json.dumps(new_metrics, indent=2)}

Provide comparison in JSON:
- summary: 1-2 sentence comparison
- improvements: list of metrics that improved
- regressions: list of metrics that got worse
- verdict: "Better", "Worse", or "Similar"
- recommendation: Trade the new version? Why or why not?

RESPOND ONLY WITH VALID JSON, NO MARKDOWN.
"""
        
        try:
            response = self.gpt.client.chat.completions.create(
                model=self.gpt.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=400
            )
            
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            result = json.loads(text)
            logger.info(f"Comparison verdict: {result.get('verdict', 'N/A')}")
            return result
        
        except Exception as e:
            logger.error(f"Comparison failed: {e}")
            return {"summary": f"Comparison failed: {str(e)}"}

    def generate_backtest_report(
        self,
        results: Dict[str, Any],
        filepath: Optional[str] = None
    ) -> str:
        """
        Generate a full backtest report with analysis.
        
        Args:
            results: Backtest results
            filepath: Optional save path
        
        Returns:
            Report as markdown string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metrics = self.extract_key_metrics(results)
        analysis = self.analyze_results(results)
        suggestions = self.get_improvement_suggestions(results)
        
        report = f"""# Backtest Analysis Report
Generated: {timestamp}

## Key Metrics
{self._format_metrics_table(metrics)}

## Analysis
{analysis.get('performance_assessment', 'N/A')}

### Strengths
{analysis.get('strengths', 'N/A')}

### Weaknesses
{analysis.get('weaknesses', 'N/A')}

### Risk Assessment
{analysis.get('risk_assessment', 'N/A')}

## Improvement Suggestions
{self._format_suggestions(suggestions)}

---
*Report generated by ChatGPT-powered Backtest Analyzer*
"""
        
        if filepath:
            try:
                Path(filepath).write_text(report)
                logger.info(f"Report saved to: {filepath}")
            except Exception as e:
                logger.error(f"Failed to save report: {e}")
        
        return report

    @staticmethod
    def _format_metrics_table(metrics: Dict[str, Any]) -> str:
        """Format metrics as markdown table."""
        if not metrics:
            return "No metrics available."
        
        rows = []
        for key, value in metrics.items():
            if isinstance(value, float):
                formatted_value = f"{value:.2%}" if 0 <= value <= 1 else f"{value:.2f}"
            else:
                formatted_value = str(value)
            rows.append(f"| {key.replace('_', ' ').title()} | {formatted_value} |")
        
        table = "| Metric | Value |\n|---|---|\n" + "\n".join(rows)
        return table

    @staticmethod
    def _format_suggestions(suggestions: List[str]) -> str:
        """Format suggestions as markdown list."""
        if not suggestions:
            return "No suggestions generated."
        return "\n".join(f"- {s}" for s in suggestions)


if __name__ == "__main__":
    print("Testing Backtest Analyzer...")
    
    try:
        analyzer = BacktestAnalyzer()
        
        # Mock results
        mock_results = {
            "Total Trades": 150,
            "Win Rate": 0.65,
            "Profit Factor": 2.15,
            "Max Drawdown": "12.5%",
            "Sharpe Ratio": 1.42,
            "Total P&L": "$5250"
        }
        
        print("\n1. Extracted Metrics:")
        metrics = analyzer.extract_key_metrics(mock_results)
        for k, v in metrics.items():
            print(f"   {k}: {v}")
        
        print("\n2. Analysis:")
        if analyzer.gpt:
            analysis = analyzer.analyze_results(mock_results)
            print(f"   {analysis.get('performance_assessment', 'N/A')}")
        else:
            print("   (GPT not available)")
        
        print("\n✓ Backtest analyzer ready!")
    
    except Exception as e:
        print(f"✗ Test failed: {e}")
