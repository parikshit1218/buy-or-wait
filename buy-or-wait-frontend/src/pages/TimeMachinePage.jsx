import React, { useState, useEffect } from 'react';
import { Card, PrimaryButton, OutlinedButton, Input } from '../components';
import { getTimeMachine } from '../api';
import { formatINR } from '../utils/currencyFormatter';
import { Play, CheckCircle2, XCircle } from 'lucide-react';

export function TimeMachinePage({ initialRequestId = 'request_07' }) {
  const [requestId, setRequestId] = useState(initialRequestId);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const sampleRequestPills = [
    { id: 'request_07', label: 'Req 07 (Rental Deposit - ₹1.97L)' },
    { id: 'request_33', label: 'Req 33 (Flat Move - ₹1.18L)' },
    { id: 'request_42', label: 'Req 42 (Urgent Repair - ₹52k)' },
    { id: 'request_46', label: 'Req 46 (Debt Repay - ₹49k)' },
    { id: 'request_48', label: 'Req 48 (Family Transfer - ₹45k)' },
  ];

  useEffect(() => {
    if (requestId) {
      loadTimeMachine(requestId);
    }
  }, [requestId]);

  const loadTimeMachine = async (reqId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getTimeMachine(reqId.trim());
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to load Time Machine scenario data.');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    if (requestId) {
      loadTimeMachine(requestId);
    }
  };

  const scenarioStyles = {
    BUY_NOW: {
      color: '#163300',
      label: 'Buy Now',
      description: '100% upfront on request date',
    },
    WAIT: {
      color: '#054d28',
      label: 'Wait',
      description: 'Deferred to earliest safe full date',
    },
    PARTIAL_PAYMENT: {
      color: '#0b4c72',
      label: 'Partial Payment',
      description: 'Pay safe amount today, remainder later',
    },
    INSTALLMENTS: {
      color: '#9fe870',
      label: 'Installments',
      description: 'Split into supplier-approved milestones',
    },
  };

  const generateTrajectoryPoints = () => {
    if (!data || !data.scenarios) return [];

    const availableBal = parseFloat(data.available_balance || 0);
    const minBal = parseFloat(data.minimum_balance_to_keep || 0);
    const dayIntervals = [0, 10, 20, 30, 45, 60, 75, 90];

    return dayIntervals.map((d) => {
      const point = { day: d };
      const payrollBump = d >= 25 ? availableBal * 0.4 : 0;
      const secondPayroll = d >= 55 ? availableBal * 0.4 : 0;
      const baseline = availableBal - (d * (availableBal * 0.005)) + payrollBump + secondPayroll;
      point.baseline = baseline;
      point.minKeep = minBal;

      data.scenarios.forEach((s) => {
        const scKey = s.scenario_name.startsWith('INSTALLMENTS') ? 'INSTALLMENTS' : s.scenario_name;
        const totalPaid = parseFloat(s.total_amount_paid || 0);
        const lowestBal = parseFloat(s.lowest_balance || 0);

        if (scKey === 'BUY_NOW') {
          point[scKey] = Math.max(lowestBal, baseline - totalPaid);
        } else if (scKey === 'WAIT') {
          const isAfterWait = d >= 30;
          point[scKey] = isAfterWait ? Math.max(lowestBal, baseline - totalPaid) : baseline;
        } else if (scKey === 'PARTIAL_PAYMENT') {
          const initialCut = totalPaid * 0.5;
          const secondCut = d >= 30 ? totalPaid * 0.5 : 0;
          point[scKey] = Math.max(lowestBal, baseline - (initialCut + secondCut));
        } else if (scKey === 'INSTALLMENTS') {
          const cuts = (d < 30 ? 1 : d < 60 ? 2 : 3) * (totalPaid / 3);
          point[scKey] = Math.max(lowestBal, baseline - cuts);
        }
      });

      return point;
    });
  };

  const trajectoryPoints = generateTrajectoryPoints();

  let chartMin = 0;
  let chartMax = 100000;
  if (data && trajectoryPoints.length > 0) {
    const allVals = [];
    trajectoryPoints.forEach((p) => {
      Object.keys(p).forEach((k) => {
        if (k !== 'day') allVals.push(p[k]);
      });
    });
    const rawMin = Math.min(...allVals);
    const rawMax = Math.max(...allVals);
    chartMin = Math.max(0, Math.floor(rawMin * 0.8));
    chartMax = Math.ceil(rawMax * 1.1);
  }

  const svgWidth = 800;
  const svgHeight = 320;
  const padX = 60;
  const padY = 30;

  const scaleX = (day) => padX + (day / 90) * (svgWidth - padX * 2);
  const scaleY = (val) => svgHeight - padY - ((val - chartMin) / (chartMax - chartMin || 1)) * (svgHeight - padY * 2);

  return (
    <div className="space-y-10 py-6 max-w-[1100px] mx-auto">
      {/* Header */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="h-2.5 w-2.5 rounded-full bg-signal-blue animate-pulse"></span>
            <p className="text-micro font-bold uppercase tracking-wider text-pebble">
              Financial Time Machine
            </p>
          </div>
          <h1 className="font-display-wise text-subheading md:text-heading text-forest-ink leading-[1.05]">
            90-DAY SCENARIO TRAJECTORY
          </h1>
          <p className="mt-3 text-body text-charcoal max-w-xl">
            Compare prospective decision paths (Buy Now vs Wait vs Installments) over 90 days with exact liquidity floors.
          </p>
        </div>

        {/* Request ID Input Form */}
        <form onSubmit={handleFormSubmit} className="flex items-center gap-2 shrink-0">
          <Input
            value={requestId}
            onChange={(e) => setRequestId(e.target.value)}
            placeholder="e.g. request_07"
            className="w-40 md:w-48 bg-paper text-body-sm font-bold"
          />
          <PrimaryButton type="submit" disabled={loading}>
            <Play className="h-4 w-4 mr-1.5 fill-current" />
            Simulate
          </PrimaryButton>
        </form>
      </section>

      {/* Quick Select Benchmark Pills */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-micro font-bold uppercase text-slate mr-2">Quick Scenarios:</span>
        {sampleRequestPills.map((pill) => (
          <button
            key={pill.id}
            onClick={() => setRequestId(pill.id)}
            className={`rounded-full px-4 py-1.5 text-caption font-medium transition-all duration-200 ease-out hover:scale-105 active:scale-95 cursor-pointer ${
              requestId === pill.id
                ? 'bg-forest-ink text-paper font-bold shadow-sm'
                : 'bg-fog text-charcoal hover:bg-linen-mist hover:text-forest-ink'
            }`}
          >
            {pill.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-[10px] bg-alarm-red/10 p-4 text-caption text-alarm-red border border-alarm-red/20 animate-verdict-slide-in">
          {error}
        </div>
      )}

      {loading && (
        <div className="rounded-cards bg-fog p-12 text-center text-body font-medium text-forest-ink">
          <span className="inline-block animate-spin mr-2">⏳</span> Loading 90-Day Time Machine Simulation...
        </div>
      )}

      {data && !loading && (
        <div className="space-y-8 animate-verdict-slide-in">
          {/* Main Interactive Chart Card */}
          <Card className="p-6 md:p-8 bg-paper border border-fog shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <div>
                <h2 className="text-body-lg font-bold text-obsidian">
                  Balance Trajectory Comparison (₹)
                </h2>
                <p className="text-caption text-slate">
                  Request: <span className="font-bold text-forest-ink">{data.request_id}</span> ({data.user_id}) — Amount: {formatINR(data.requested_amount)}
                </p>
              </div>

              {/* Legend */}
              <div className="flex flex-wrap items-center gap-4 text-micro font-bold">
                <div className="flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded-full bg-forest-ink"></span>
                  <span className="text-forest-ink">Buy Now</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded-full bg-spruce"></span>
                  <span className="text-spruce">Wait</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded-full bg-signal-blue"></span>
                  <span className="text-signal-blue">Partial</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-3 w-3 rounded-full bg-lime-voltage border border-forest-ink"></span>
                  <span className="text-charcoal">Installments</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-alarm-red border-b border-dashed"></span>
                  <span className="text-alarm-red">Min Floor</span>
                </div>
              </div>
            </div>

            {/* SVG Line Chart Container */}
            <div className="relative overflow-x-auto w-full">
              <svg
                viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                className="w-full h-auto min-w-[600px]"
              >
                {/* Grid horizontal lines */}
                {[0, 0.25, 0.5, 0.75, 1].map((ratio, idx) => {
                  const y = padY + ratio * (svgHeight - padY * 2);
                  const val = chartMax - ratio * (chartMax - chartMin);
                  return (
                    <g key={idx}>
                      <line
                        x1={padX}
                        y1={y}
                        x2={svgWidth - padX}
                        y2={y}
                        stroke="#e8ebe6"
                        strokeWidth="1"
                      />
                      <text
                        x={padX - 8}
                        y={y + 4}
                        textAnchor="end"
                        className="text-[10px] fill-pebble font-medium"
                      >
                        {formatINR(Math.round(val))}
                      </text>
                    </g>
                  );
                })}

                {/* Grid vertical date lines (Day 0, 30, 60, 90) */}
                {[0, 30, 60, 90].map((d) => {
                  const x = scaleX(d);
                  return (
                    <g key={d}>
                      <line
                        x1={x}
                        y1={padY}
                        x2={x}
                        y2={svgHeight - padY}
                        stroke="#e8ebe6"
                        strokeWidth="1"
                      />
                      <text
                        x={x}
                        y={svgHeight - padY + 16}
                        textAnchor="middle"
                        className="text-[11px] fill-slate font-bold"
                      >
                        Day {d}
                      </text>
                    </g>
                  );
                })}

                {/* Minimum Balance Protected Line */}
                <line
                  x1={padX}
                  y1={scaleY(parseFloat(data.minimum_balance_to_keep))}
                  x2={svgWidth - padX}
                  y2={scaleY(parseFloat(data.minimum_balance_to_keep))}
                  stroke="#cb272f"
                  strokeWidth="2"
                  strokeDasharray="4 4"
                />

                {/* Trajectory Curves for each scenario */}
                {['BUY_NOW', 'WAIT', 'PARTIAL_PAYMENT', 'INSTALLMENTS'].map((scKey) => {
                  const points = trajectoryPoints.map((p) => `${scaleX(p.day)},${scaleY(p[scKey] || p.baseline)}`).join(' ');
                  const strokeCol =
                    scKey === 'BUY_NOW'
                      ? '#163300'
                      : scKey === 'WAIT'
                      ? '#054d28'
                      : scKey === 'PARTIAL_PAYMENT'
                      ? '#0b4c72'
                      : '#9fe870';

                  return (
                    <g key={scKey}>
                      <polyline
                        fill="none"
                        stroke={strokeCol}
                        strokeWidth={scKey === 'BUY_NOW' ? '3' : '2.5'}
                        points={points}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      {trajectoryPoints.map((p, pIdx) => (
                        <circle
                          key={pIdx}
                          cx={scaleX(p.day)}
                          cy={scaleY(p[scKey] || p.baseline)}
                          r={scKey === 'BUY_NOW' ? 4 : 3}
                          fill={strokeCol}
                          className="transition-all hover:r-6 cursor-pointer"
                        />
                      ))}
                    </g>
                  );
                })}
              </svg>
            </div>
          </Card>

          {/* Scenario Comparison Cards */}
          <div>
            <h3 className="text-body-lg font-bold text-obsidian mb-4">
              Simulated Scenario Outcomes
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {data.scenarios.map((sc, idx) => {
                const scType = sc.scenario_name.startsWith('INSTALLMENTS')
                  ? 'INSTALLMENTS'
                  : sc.scenario_name;
                const style = scenarioStyles[scType] || { label: sc.scenario_name, color: '#163300' };

                return (
                  <Card
                    key={idx}
                    className={`flex flex-col justify-between border transition-all ${
                      sc.is_safe ? 'border-lime-voltage/40 bg-paper' : 'border-fog bg-fog'
                    }`}
                  >
                    <div>
                      {/* Header with Safe Badge */}
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-bold text-body text-forest-ink">
                          {style.label}
                        </span>
                        {sc.is_safe ? (
                          <span className="rounded-tags bg-linen-mist px-2.5 py-0.5 text-micro font-bold text-forest-ink flex items-center gap-1">
                            <CheckCircle2 className="h-3 w-3 text-forest-ink" /> SAFE
                          </span>
                        ) : (
                          <span className="rounded-tags bg-alarm-red/10 px-2.5 py-0.5 text-micro font-bold text-alarm-red flex items-center gap-1">
                            <XCircle className="h-3 w-3 text-alarm-red" /> UNSAFE
                          </span>
                        )}
                      </div>

                      {/* Lowest Balance & Safety Margin */}
                      <div className="space-y-3 mt-4">
                        <div>
                          <span className="text-micro font-bold uppercase text-pebble block">
                            Lowest Balance
                          </span>
                          <p className="text-body-lg font-bold text-obsidian">
                            {formatINR(sc.lowest_balance)}
                          </p>
                          <span className="text-micro text-slate">
                            on {sc.lowest_balance_date || 'N/A'}
                          </span>
                        </div>

                        <div>
                          <span className="text-micro font-bold uppercase text-pebble block">
                            Safety Margin
                          </span>
                          <p className={`text-body font-bold ${sc.is_safe ? 'text-forest-ink' : 'text-alarm-red'}`}>
                            {formatINR(sc.safety_margin)}
                          </p>
                        </div>

                        <div>
                          <span className="text-micro font-bold uppercase text-pebble block">
                            Total Paid
                          </span>
                          <p className="text-body font-bold text-charcoal">
                            {formatINR(sc.total_amount_paid)}
                          </p>
                          <span className="text-micro text-slate">
                            in {sc.number_of_payments} payment{sc.number_of_payments > 1 ? 's' : ''}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Completion Date */}
                    <div className="mt-4 pt-3 border-t border-fog flex items-center justify-between text-caption text-slate">
                      <span>Completion:</span>
                      <span className="font-bold text-forest-ink">
                        {sc.completion_date || 'N/A'}
                      </span>
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TimeMachinePage;
