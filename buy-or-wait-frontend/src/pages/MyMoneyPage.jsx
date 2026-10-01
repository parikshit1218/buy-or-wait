import React, { useState, useEffect } from 'react';
import { Card, PrimaryButton, OutlinedButton, Input } from '../components';
import { getHealth } from '../api';
import { formatINR } from '../utils/currencyFormatter';
import { Wallet, ArrowDownRight, ArrowUpRight, ShieldCheck, Check } from 'lucide-react';

export function MyMoneyPage({ onNavigate }) {
  const [healthStatus, setHealthStatus] = useState({ loading: true, data: null, error: null });

  // Default financial state (from user_07 benchmark profile)
  const [finances, setFinances] = useState(() => {
    const saved = localStorage.getItem('buy_or_wait_user_finances');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        // ignore
      }
    }
    return {
      available_balance: '218945',
      min_balance: '93000',
      monthly_salary: '145000',
      rent: '35000',
      food: '15000',
      utilities: '6500',
      subscriptions: '3200',
      other_expenses: '8000',
    };
  });

  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    localStorage.setItem('buy_or_wait_user_finances', JSON.stringify(finances));
  }, [finances]);

  useEffect(() => {
    getHealth()
      .then((data) => setHealthStatus({ loading: false, data, error: null }))
      .catch((err) => setHealthStatus({ loading: false, data: null, error: err.message }));
  }, []);

  const handleChange = (field, value) => {
    setFinances((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = (e) => {
    e.preventDefault();
    localStorage.setItem('buy_or_wait_user_finances', JSON.stringify(finances));
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 2500);
  };

  // Computations
  const totalIncome = parseFloat(finances.monthly_salary || 0);
  const totalExpenses =
    parseFloat(finances.rent || 0) +
    parseFloat(finances.food || 0) +
    parseFloat(finances.utilities || 0) +
    parseFloat(finances.subscriptions || 0) +
    parseFloat(finances.other_expenses || 0);
  const netSurplus = totalIncome - totalExpenses;
  const availableBal = parseFloat(finances.available_balance || 0);
  const minKeep = parseFloat(finances.min_balance || 0);

  const inrBenchmarkRequests = [
    { id: 'request_07', item: 'Rental Deposit', amount: 197400, type: 'Housing' },
    { id: 'request_33', item: 'New Flat Deposit', amount: 118000, type: 'Housing' },
    { id: 'request_42', item: 'Urgent Vehicle Repair', amount: 52100, type: 'Emergency' },
    { id: 'request_46', item: 'Loan Prepayment', amount: 49450, type: 'Debt' },
  ];

  return (
    <div className="space-y-10 py-6">
      {/* Header */}
      <section className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-fog/60 p-6 md:p-8 rounded-largecards border border-forest-ink/5 shadow-subtle">
        <div className="flex items-start sm:items-center gap-4 sm:gap-5">
          <div className="shrink-0 h-14 w-14 rounded-full bg-forest-ink flex items-center justify-center text-lime-voltage shadow-md border-2 border-lime-voltage/30">
            <Wallet className="h-7 w-7" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="h-2.5 w-2.5 rounded-full bg-lime-voltage animate-pulse"></span>
              <p className="text-micro font-bold uppercase tracking-wider text-pebble">
                My Money · Cashflow & Reserve Baseline
              </p>
            </div>
            <h1 className="font-display-wise text-subheading md:text-heading-sm lg:text-heading text-forest-ink leading-[1.05]">
              FINANCIAL STATE & BUDGET
            </h1>
            <p className="mt-2 text-body text-charcoal max-w-2xl">
              Track your available liquid cash, protected emergency reserve, and recurring monthly budget in Indian Rupees (₹).
            </p>
          </div>
        </div>

        <div className="shrink-0 self-end md:self-center">
          <PrimaryButton onClick={() => onNavigate('can-i-buy-this')}>
            Check a Purchase
          </PrimaryButton>
        </div>
      </section>

      {/* Financial State Metric Cards */}
      <section className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {/* Available Balance */}
        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-caption font-bold uppercase text-slate">Available Balance</span>
              <span className="h-2.5 w-2.5 rounded-full bg-lime-voltage"></span>
            </div>
            <p className="mt-4 font-display-wise text-subheading text-forest-ink">
              {formatINR(availableBal)}
            </p>
          </div>
          <p className="mt-4 text-micro text-slate">
            Current liquid balance
          </p>
        </Card>

        {/* Protected Minimum Floor */}
        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-caption font-bold uppercase text-slate">Protected Floor</span>
              <span className="h-2.5 w-2.5 rounded-full bg-alarm-red"></span>
            </div>
            <p className="mt-4 font-display-wise text-subheading text-obsidian">
              {formatINR(minKeep)}
            </p>
          </div>
          <p className="mt-4 text-micro text-slate">
            Hard minimum reserve threshold
          </p>
        </Card>

        {/* Monthly Inflow vs Outflow */}
        <Card className="flex flex-col justify-between bg-linen-mist/40 border border-lime-voltage/30">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-caption font-bold uppercase text-forest-ink">Monthly Net Flow</span>
              <span className="rounded-tags bg-lime-voltage px-2.5 py-0.5 text-micro font-bold text-charcoal">
                SURPLUS
              </span>
            </div>
            <p className="mt-4 font-display-wise text-subheading text-forest-ink">
              {formatINR(netSurplus)}
            </p>
          </div>
          <p className="mt-4 text-micro text-forest-ink font-medium">
            Income ({formatINR(totalIncome)}) – Expenses ({formatINR(totalExpenses)})
          </p>
        </Card>

        {/* Backend Connectivity Status */}
        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-caption font-bold uppercase text-slate">Engine Status</span>
              <span className="text-micro font-medium text-slate">FastAPI</span>
            </div>
            <div className="mt-4 flex items-center gap-3">
              {healthStatus.loading ? (
                <span className="text-body font-bold text-slate">Connecting...</span>
              ) : healthStatus.error ? (
                <span className="text-body font-bold text-alarm-red">Offline</span>
              ) : (
                <span className="text-body font-bold text-forest-ink">Online & Synced</span>
              )}
            </div>
          </div>
          <p className="mt-4 text-micro text-slate">
            Deterministic 90-day model active
          </p>
        </Card>
      </section>

      {/* Monthly Budget Input Form */}
      <section className="rounded-cards bg-fog p-6 md:p-8 shadow-subtle">
        <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-body-lg font-bold text-obsidian">
              Monthly Budget & Recurring Commitments
            </h2>
            <p className="text-caption text-slate">
              Enter your regular monthly income and expenses. These numbers ground the 90-day cashflow forecast.
            </p>
          </div>
          {savedSuccess && (
            <span className="rounded-tags bg-linen-mist text-forest-ink px-4 py-1.5 text-caption font-bold flex items-center gap-1.5">
              <Check className="h-4 w-4 text-forest-ink" /> Budget Saved
            </span>
          )}
        </div>

        <form onSubmit={handleSave} className="space-y-6">
          {/* Liquid Balances Section */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pb-6 border-b border-fog/80">
            <div>
              <label className="text-caption font-bold text-forest-ink block mb-2">
                Available Liquid Cash (₹)
              </label>
              <Input
                type="number"
                min="0"
                value={finances.available_balance}
                onChange={(e) => handleChange('available_balance', e.target.value)}
                placeholder="218945"
              />
              <span className="text-micro text-slate mt-1 block">Current balance in bank account</span>
            </div>

            <div>
              <label className="text-caption font-bold text-forest-ink block mb-2">
                Protected Minimum Floor to Keep (₹)
              </label>
              <Input
                type="number"
                min="0"
                value={finances.min_balance}
                onChange={(e) => handleChange('min_balance', e.target.value)}
                placeholder="93000"
              />
              <span className="text-micro text-slate mt-1 block">Emergency floor that must never be breached</span>
            </div>
          </div>

          {/* Income & Expenses Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
            <div>
              <label className="text-caption font-bold text-forest-ink block mb-2 flex items-center gap-1.5">
                <ArrowUpRight className="h-4 w-4 text-forest-ink" /> Monthly Inflow / Salary (₹)
              </label>
              <Input
                type="number"
                min="0"
                value={finances.monthly_salary}
                onChange={(e) => handleChange('monthly_salary', e.target.value)}
                placeholder="145000"
              />
            </div>

            <div>
              <label className="text-caption font-bold text-slate block mb-2 flex items-center gap-1.5">
                <ArrowDownRight className="h-4 w-4 text-pebble" /> Rent / Housing (₹)
              </label>
              <Input
                type="number"
                min="0"
                value={finances.rent}
                onChange={(e) => handleChange('rent', e.target.value)}
                placeholder="35000"
              />
            </div>

            <div>
              <label className="text-caption font-bold text-slate block mb-2">
                Food & Groceries (₹)
              </label>
              <Input
                type="number"
                min="0"
                value={finances.food}
                onChange={(e) => handleChange('food', e.target.value)}
                placeholder="15000"
              />
            </div>

            <div>
              <label className="text-caption font-bold text-slate block mb-2">
                Utilities & Bills (₹)
              </label>
              <Input
                type="number"
                min="0"
                value={finances.utilities}
                onChange={(e) => handleChange('utilities', e.target.value)}
                placeholder="6500"
              />
            </div>

            <div>
              <label className="text-caption font-bold text-slate block mb-2">
                Subscriptions & Streaming (₹)
              </label>
              <Input
                type="number"
                min="0"
                value={finances.subscriptions}
                onChange={(e) => handleChange('subscriptions', e.target.value)}
                placeholder="3200"
              />
            </div>

            <div>
              <label className="text-caption font-bold text-slate block mb-2">
                Other Flexible Debits (₹)
              </label>
              <Input
                type="number"
                min="0"
                value={finances.other_expenses}
                onChange={(e) => handleChange('other_expenses', e.target.value)}
                placeholder="8000"
              />
            </div>
          </div>

          {/* Action Row */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-fog/80">
            <div className="text-body-sm font-bold text-forest-ink">
              Total Fixed Expenses: <span className="text-obsidian">{formatINR(totalExpenses)}</span> / month
            </div>
            <PrimaryButton type="submit">
              Save Monthly Budget
            </PrimaryButton>
          </div>
        </form>
      </section>

      {/* 90-Day Liquidity Forecast Overview */}
      <section className="rounded-cards bg-paper p-6 md:p-8 border border-fog shadow-subtle">
        <h2 className="text-body-lg font-bold text-obsidian mb-2">
          90-Day Cashflow Dynamics
        </h2>
        <p className="text-caption text-slate mb-6">
          How your liquidity evolves over the next 3 months with confirmed payroll and recurring expenses.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-[10px] bg-fog p-5">
            <span className="text-micro font-bold uppercase text-slate block mb-1">Day 0 – 30</span>
            <p className="text-body font-bold text-forest-ink">Immediate Buffer</p>
            <p className="text-caption text-slate mt-2">
              Next confirmed payroll arrives on schedule. Essential living commitments fully covered.
            </p>
          </div>

          <div className="rounded-[10px] bg-fog p-5">
            <span className="text-micro font-bold uppercase text-slate block mb-1">Day 30 – 60</span>
            <p className="text-body font-bold text-forest-ink">Mid-Term Inflow</p>
            <p className="text-caption text-slate mt-2">
              Second payroll cycle reinforces available balance above the {formatINR(minKeep)} minimum keep threshold.
            </p>
          </div>

          <div className="rounded-[10px] bg-fog p-5">
            <span className="text-micro font-bold uppercase text-slate block mb-1">Day 60 – 90</span>
            <p className="text-body font-bold text-forest-ink">Long-Term Recovery</p>
            <p className="text-caption text-slate mt-2">
              Full liquidity recovery with flexible spending categories intact.
            </p>
          </div>
        </div>
      </section>

      {/* Benchmark Reference Requests */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-body-lg font-bold text-obsidian">Reference Decision Requests</h2>
          <span className="text-caption text-slate">1-Click simulation</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {inrBenchmarkRequests.map((req) => (
            <div
              key={req.id}
              className="rounded-cards bg-paper p-5 border border-fog shadow-subtle flex items-center justify-between hover:border-pebble transition-colors"
            >
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-caption font-bold text-forest-ink">{req.id}</span>
                  <span className="rounded-tags bg-fog px-2 py-0.5 text-micro font-medium text-slate">
                    {req.type}
                  </span>
                </div>
                <p className="text-body font-bold text-obsidian">
                  {req.item} — {formatINR(req.amount)}
                </p>
              </div>

              <PrimaryButton
                onClick={() =>
                  onNavigate('can-i-buy-this', {
                    item: req.item,
                    amount: req.amount,
                    request_id: req.id,
                  })
                }
                className="px-4 py-2 text-caption"
              >
                Evaluate
              </PrimaryButton>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default MyMoneyPage;
