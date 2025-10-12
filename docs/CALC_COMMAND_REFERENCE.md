# /calc Command Reference

Quick reference for the `/calc` Discord command strike formats.

## Strike Format Rules

**Simple Rule:** The format tells you the strike order, the strategy tells you which is long/short.

| Strategy | Format | 1st Strike | 2nd Strike | Example |
|----------|--------|------------|------------|---------|
| **Bull Call Spread (Debit)** | `lower/higher` | Long | Short | `445/450` |
| **Bear Put Spread (Debit)** | `higher/lower` | Long | Short | `450/445` |
| **Bull Put Spread (Credit)** | `higher/lower` | Short | Long | `450/445` |
| **Bear Call Spread (Credit)** | `lower/higher` | Short | Long | `445/450` |
| **Long Call** | Single | N/A | N/A | `450` |
| **Long Put** | Single | N/A | N/A | `450` |

## Memory Aid

**Debit Spreads:**
- Debit Call: `lower/higher` (buy cheaper, sell expensive)
- Debit Put: `higher/lower` (buy expensive, sell cheaper)

**Credit Spreads:**
- Credit Call: `lower/higher` (sell cheap, buy expensive protection)
- Credit Put: `higher/lower` (sell expensive, buy cheap protection)

## Discord Command Examples

### Debit Spreads (Pay premium upfront)

**Bull Call Spread:**
```
/calc
Strategy: Bull Call Spread (Debit)
Symbol: SPY
Strikes: 540/545
DTE: 7
```
- Buys 540 call (long)
- Sells 545 call (short)
- Cost: Debit paid
- Max profit: Strike difference - debit

**Bear Put Spread:**
```
/calc
Strategy: Bear Put Spread (Debit)
Symbol: SPY
Strikes: 550/545
DTE: 7
```
- Buys 550 put (long)
- Sells 545 put (short)
- Cost: Debit paid
- Max profit: Strike difference - debit

### Credit Spreads (Receive premium upfront)

**Bull Put Spread (Credit):**
```
/calc
Strategy: Bull Put Spread (Credit)
Symbol: SPY
Strikes: 545/540
DTE: 7
```
- Sells 545 put (short)
- Buys 540 put (long)
- Credit: Premium received
- Max profit: Credit
- Max loss: Strike difference - credit
- Profit if price stays above 545 (short strike)

**Bear Call Spread (Credit):**
```
/calc
Strategy: Bear Call Spread (Credit)
Symbol: SPY
Strikes: 545/550
DTE: 7
```
- Sells 545 call (short)
- Buys 550 call (long)
- Credit: Premium received
- Max profit: Credit
- Max loss: Strike difference - credit
- Profit if price stays below 545 (short strike)

### Long Options

**Long Call:**
```
/calc
Strategy: Long Call
Symbol: SPY
Strikes: 540
DTE: 7
```

**Long Put:**
```
/calc
Strategy: Long Put
Symbol: SPY
Strikes: 540
DTE: 7
```

## Error Messages

If you use the wrong format, you'll see helpful errors:

```
❌ Bull Call Spread: Format is 'lower/higher' (e.g., '445/450')
You entered: 450/445
```

```
❌ Bear Put Spread: Format is 'higher/lower' (e.g., '450/445')
You entered: 445/450
```

## ICT Context

The bot adds ICT methodology context for each spread:

- **Bull Call Spread:** "Best after SSL sweep + bullish displacement"
- **Bear Put Spread:** "Best after BSL sweep + bearish displacement"
- **Bull Put Spread:** "Profit if price stays above short strike (bullish/neutral)"
- **Bear Call Spread:** "Profit if price stays below short strike (bearish/neutral)"

## Tips

1. **Symbol autocomplete:** Type first few letters of ticker, bot suggests 515 S&P 500 + ETF tickers
2. **Premium optional:** If omitted, bot fetches current market price
3. **DTE validation:** Must be between 1-365 days
4. **Credit spreads:** Show green embed
5. **Debit spreads:** Show blue embed
6. **Visual output:** Displays max profit/loss, breakeven, R:R, POP

## Your Original Question

**You asked:** "I tried this command: `/calc Vertical Spread SPY 650/649 put 1`"

**With new version:**

For Bear Put Spread (Debit):
```
/calc
Strategy: Bear Put Spread (Debit)
Symbol: SPY
Strikes: 650/649
DTE: 1
```

For Bull Put Spread (Credit):
```
/calc
Strategy: Bull Put Spread (Credit)
Symbol: SPY
Strikes: 650/649
DTE: 1
```

No more confusion about which is which!
