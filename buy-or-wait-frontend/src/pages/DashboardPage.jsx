import React, { useState, useEffect } from 'react';
import { Card, PrimaryButton, OutlinedButton } from '../components';
import { getHealth } from '../api';
import { formatINR } from '../utils/currencyFormatter';

export function DashboardPage({ onNavigate }) {
  const [healthStatus, setHealthStatus] = useState({ loading: true, data: null, error: null });

  // Default native INR financial profile (user_07 from dataset)
  const defaultFinancials = {
    user_id: 'user_07',
    available_balance: 218945.56,
    min_balance: 93000.0,
    monthly_income: 145000.0,
    monthly_expenses: 52000.0,
  };

  const inrBenchmarkRequests = [
    { id: 'request_07', item: 'Rental Deposit', amount: 197400, status: 'affordable_with_plan', type: 'Housing' },
    { id: 'request_33', item: 'New Flat Deposit', amount: 118000, status: 'affordable_later', type: 'Housing' },
    { id: 'request_42', item: 'Urgent Vehicle Repair', amount: 52100, status: 'affordable_now', type: 'Emergency' },
    { id: 'request_46', item: 'Loan Prepayment', amount: 49450, status: 'affordable_now', type: 'Debt' },
  ];

  useEffect(() => {
    getHealth()
      .then((data) => setHealthStatus({ loading: false, data, error: null }))
      .catch((err) => setHealthStatus({ loading: false, data: null, error: err.message }));
  }, []);

  return (
    <div className="space-y-10 py-6">
      {/* Hero Headline per DESIGN.md */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="h-2.5 w-2.5 rounded-full bg-lime-voltage"></span>
            <p className="text-micro font-bold uppercase tracking-wider text-pebble">
              Deterministic Financial Health Engine
            </p>
          </div>
          <h1 className="font-display-wise text-subheading md:text-heading text-forest-ink leading-[1.05]">
            FINANCIAL STATE & 90-DAY FORECAST
          </h1>
          <p className="mt-3 text-body text-charcoal max-w-2xl">
            Real-time balance reconstruction with protected minimum floors and multi-scenario cashflow safety checks.
          </p>
        </div>
      </section>

      {/* Financial State Metric Cards Grid */}
      <section className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {/* Available Balance */}
        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-caption font-bold uppercase text-slate">Available Balance</span>
              <span className="h-2 w-2 rounded-full bg-lime-voltage"></span>
            </div>
            <p className="mt-4 font-display-wise text-subheading text-forest-ink">
              {formatINR(defaultFinancials.available_balance)}
            </p>
          </div>
          <p className="mt-4 text-micro text-slate">
            Reconstructed from cash ledger
          </p>
        </Card>

        {/* Protected Minimum Balance */}
        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-caption font-bold uppercase text-slate">Protected Floor</span>
              <span className="h-2 w-2 rounded-full bg-alarm-red"></span>
            </div>
            <p className="mt-4 font-display-wise text-subheading text-obsidian">
              {formatINR(defaultFinancials.min_balance)}
            </p>
          </div>
          <p className="mt-4 text-micro text-slate">
            Hard safety barrier (never breached)
          </p>
        </Card>

        {/* 90-Day Forecast Safety Buffer */}
        <Card className="flex flex-col justify-between bg-linen-mist/50 border border-lime-voltage/30">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-caption font-bold uppercase text-forest-ink">90-Day Horizon</span>
              <span className="rounded-tags bg-lime-voltage px-2.5 py-0.5 text-micro font-bold text-charcoal">
                ACTIVE
              </span>
            </div>
            <p className="mt-4 font-display-wise text-subheading text-forest-ink">
              90 Days
            </p>
          </div>
          <p className="mt-4 text-micro text-forest-ink font-medium">
            Forward cashflow projection active
          </p>
        </Card>

        {/* Backend API Status */}
        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-caption font-bold uppercase text-slate">Backend Service</span>
              <span className="text-micro font-medium text-slate">FastAPI</span>
            </div>
            <div className="mt-4 flex items-center gap-3">
              {healthStatus.loading ? (
                <span className="text-body font-bold text-slate">Connecting...</span>
              ) : healthStatus.error ? (
                <span className="text-body font-bold text-alarm-red">Offline</span>
              ) : (
                <span className="text-body font-bold text-forest-ink">Online & Ready</span>
              )}
            </div>
          </div>
          <p className="mt-4 text-micro text-slate">
            http://127.0.0.1:8000
          </p>
        </Card>
      </section>

      {/* 90-Day Forecast Milestones */}
      <section className="rounded-cards bg-fog p-6 md:p-8 shadow-subtle">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-body-lg font-bold text-obsidian">90-Day Cashflow Dynamics</h2>
            <p className="text-caption text-slate">
              Simulated deterministic liquidity milestones incorporating confirmed salaries, recurring subscriptions, and essential debits.
            </p>
          </div>
          <div className="flex gap-3">
            <PrimaryButton onClick={() => onNavigate('decision')}>
              Evaluate New Purchase
            </PrimaryButton>
            <OutlinedButton onClick={() => onNavigate('time-machine', { requestId: 'request_07' })}>
              Open Time Machine
            </OutlinedButton>
          </div>
        </div>

        {/* Milestone Timeline Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-[10px] bg-paper p-5 border border-fog">
            <span className="text-micro font-bold uppercase text-slate block mb-1">Day 0 – 30</span>
            <p className="text-body font-bold text-forest-ink">Immediate Buffer</p>
            <p className="text-caption text-slate mt-2">
              Next confirmed payroll arrives on schedule. Essential living commitments fully covered.
            </p>
          </div>

          <div className="rounded-[10px] bg-paper p-5 border border-fog">
            <span className="text-micro font-bold uppercase text-slate block mb-1">Day 30 – 60</span>
            <p className="text-body font-bold text-forest-ink">Mid-Term Inflow</p>
            <p className="text-caption text-slate mt-2">
              Second payroll cycle reinforces available balance above minimum keep threshold.
            </p>
          </div>

          <div className="rounded-[10px] bg-paper p-5 border border-fog">
            <span className="text-micro font-bold uppercase text-slate block mb-1">Day 60 – 90</span>
            <p className="text-body font-bold text-forest-ink">Long-Term Trajectory</p>
            <p className="text-caption text-slate mt-2">
              Full liquidity recovery with flexible spending categories intact.
            </p>
          </div>
        </div>
      </section>

      {/* Quick Benchmark Reference Requests (INR) */}
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

              <div className="flex items-center gap-2">
                <button
                  onClick={() => onNavigate('decision', { item: req.item, amount: req.amount, user_id: 'user_07', request_id: req.id })}
                  className="rounded-full bg-lime-voltage px-4 py-2 text-caption font-medium text-charcoal hover:opacity-90 transition cursor-pointer"
                >
                  Decide
                </button>
                <button
                  onClick={() => onNavigate('time-machine', { requestId: req.id })}
                  className="rounded-full border border-forest-ink px-4 py-2 text-caption font-medium text-forest-ink hover:bg-fog transition cursor-pointer"
                >
                  Simulate
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default DashboardPage;
