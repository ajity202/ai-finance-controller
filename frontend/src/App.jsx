import { useEffect, useMemo, useState } from "react";

const API_BASE_URL = "http://127.0.0.1:8000";

const navItems = [
  { name: "Dashboard", icon: "▦" },
  { name: "Reconciliation", icon: "⇄" },
  { name: "Exceptions", icon: "!" },
  { name: "Analytics", icon: "◫" },
  { name: "Audit Log", icon: "◷" },
];

function StatusBadge({ status }) {
  const styles = {
    RECONCILED:
      "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    RESOLVED:
      "bg-blue-500/10 text-blue-400 border-blue-500/20",
    NEEDS_REVIEW:
      "bg-amber-500/10 text-amber-400 border-amber-500/20",
    UNRESOLVED:
      "bg-red-500/10 text-red-400 border-red-500/20",
  };

  return (
    <span
      className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
        styles[status] || "bg-slate-500/10 text-slate-400 border-slate-500/20"
      }`}
    >
      {status
        ? status.replaceAll("_", " ")
        : "UNKNOWN"}
    </span>
  );
}

function StatCard({ title, value, subtitle, icon }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <div className="flex items-start justify-between">
        <p className="text-sm text-slate-400">{title}</p>

        <span className="rounded-lg bg-slate-800 px-2.5 py-1 text-slate-300">
          {icon}
        </span>
      </div>

      <p className="mt-4 text-3xl font-semibold tracking-tight">
        {value}
      </p>

      <p className="mt-2 text-xs text-slate-500">
        {subtitle}
      </p>
    </div>
  );
}

/* --------------------------------------------------
   HELPERS
-------------------------------------------------- */

function formatCurrency(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return `₹${Number(value).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;
}

function formatDifference(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  const number = Number(value);

  if (number === 0) {
    return "₹0";
  }

  return `${number > 0 ? "+" : ""}${formatCurrency(number)}`;
}

function formatConfidence(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return `${Math.round(Number(value) * 100)}%`;
}

function getTransactionLabel(tx) {
  if (tx.order_id) {
    return tx.order_id;
  }

  if (tx.order) {
    return tx.order;
  }

  return tx.unified_transaction_id || "Unknown";
}

function getExceptionLabel(tx) {
  return tx.exception_type
    ? tx.exception_type.replaceAll("_", " ")
    : "—";
}


/* --------------------------------------------------
   DASHBOARD
-------------------------------------------------- */

function Dashboard({
  summary,
  results,
  setPage,
  loading,
}) {
  const total = summary.total || 0;

  const reconciled = summary.reconciled || 0;
  const resolved = summary.resolved || 0;
  const needsReview = summary.needs_review || 0;
  const unresolved = summary.unresolved || 0;

  const exceptionCount =
    needsReview + unresolved;

  const reconciledPercentage =
    total > 0
      ? ((reconciled / total) * 100).toFixed(1)
      : "0.0";

  const needsReviewPercentage =
    total > 0
      ? ((needsReview / total) * 100).toFixed(1)
      : "0.0";

  const unresolvedPercentage =
    total > 0
      ? ((unresolved / total) * 100).toFixed(1)
      : "0.0";

  const donutReconciled =
    total > 0
      ? (reconciled / total) * 100
      : 0;

  const donutReviewEnd =
    total > 0
      ? donutReconciled + (needsReview / total) * 100
      : 0;

  const recentExceptions = results
    .filter(
      (tx) =>
        tx.final_status !== "RECONCILED"
    )
    .slice(0, 5);

  return (
    <div className="space-y-6">

      {/* KPI CARDS */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">

        <StatCard
          title="Total Transactions"
          value={loading ? "…" : total}
          subtitle="Processed transactions"
          icon="Σ"
        />

        <StatCard
          title="Reconciled"
          value={loading ? "…" : reconciled}
          subtitle={`${reconciledPercentage}% of transactions`}
          icon="✓"
        />

        <StatCard
          title="AI Resolved"
          value={loading ? "…" : resolved}
          subtitle="Resolved by AI decision layer"
          icon="✦"
        />

        <StatCard
          title="Needs Review"
          value={loading ? "…" : needsReview}
          subtitle="Finance action required"
          icon="!"
        />

        <StatCard
          title="Unresolved"
          value={loading ? "…" : unresolved}
          subtitle="Insufficient evidence"
          icon="○"
        />

      </div>


      {/* OVERVIEW + AI */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">

        {/* RECONCILIATION OVERVIEW */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 xl:col-span-2">

          <div className="flex items-center justify-between">

            <div>
              <h2 className="font-semibold">
                Reconciliation Overview
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Transaction outcome distribution
              </p>
            </div>

            <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs text-emerald-400">
              Live Data
            </span>

          </div>


          <div className="mt-8 flex items-center gap-8">

            <div
              className="flex h-44 w-44 shrink-0 items-center justify-center rounded-full"
              style={{
                background:
                  total > 0
                    ? `conic-gradient(
                        #10b981 0 ${donutReconciled}%,
                        #f59e0b ${donutReconciled}% ${donutReviewEnd}%,
                        #ef4444 ${donutReviewEnd}% 100%
                      )`
                    : "conic-gradient(#334155 0 100%)",
              }}
            >

              <div className="flex h-28 w-28 flex-col items-center justify-center rounded-full bg-slate-900">

                <span className="text-2xl font-semibold">
                  {total}
                </span>

                <span className="text-xs text-slate-500">
                  Transactions
                </span>

              </div>

            </div>


            <div className="flex-1 space-y-4">

              <div className="flex items-center justify-between">

                <div className="flex items-center gap-3">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />

                  <span className="text-sm text-slate-400">
                    Reconciled
                  </span>
                </div>

                <span className="font-medium">
                  {reconciled}
                </span>

              </div>


              <div className="flex items-center justify-between">

                <div className="flex items-center gap-3">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />

                  <span className="text-sm text-slate-400">
                    Needs Review
                  </span>
                </div>

                <span className="font-medium">
                  {needsReview}
                </span>

              </div>


              <div className="flex items-center justify-between">

                <div className="flex items-center gap-3">
                  <span className="h-2.5 w-2.5 rounded-full bg-red-400" />

                  <span className="text-sm text-slate-400">
                    Unresolved
                  </span>
                </div>

                <span className="font-medium">
                  {unresolved}
                </span>

              </div>

            </div>

          </div>

        </div>


        {/* AI AGENT */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

          <h2 className="font-semibold">
            AI Finance Agent
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Exception intelligence
          </p>


          <div className="mt-6 rounded-xl border border-blue-500/20 bg-blue-500/5 p-5">

            <div className="flex items-center gap-3">

              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400">
                ✦
              </div>

              <div>
                <p className="text-sm font-medium">
                  AI Analysis Layer
                </p>

                <p className="text-xs text-slate-500">
                  Evidence-based investigation
                </p>
              </div>

            </div>


            <p className="mt-5 text-sm leading-6 text-slate-400">
              The AI agent analyzes reconciliation exceptions,
              explains discrepancies and recommends the next
              finance action.
            </p>


            <div className="mt-4 rounded-lg bg-slate-950/60 p-3">

              <p className="text-xs text-slate-500">
                OPEN EXCEPTIONS
              </p>

              <p className="mt-1 text-xl font-semibold">
                {exceptionCount}
              </p>

            </div>


            <button
              onClick={() => setPage("Exceptions")}
              className="mt-5 w-full rounded-lg border border-slate-700 py-2.5 text-sm hover:bg-slate-800"
            >
              Review Exceptions
            </button>

          </div>

        </div>

      </div>


      {/* RECENT EXCEPTIONS */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900">

        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-5">

          <div>
            <h2 className="font-semibold">
              Recent Exceptions
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Cases requiring attention
            </p>
          </div>

          <button
            onClick={() => setPage("Exceptions")}
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            View all →
          </button>

        </div>


        {recentExceptions.length > 0 ? (
          <TransactionTable
            transactions={recentExceptions}
          />
        ) : (
          <div className="px-6 py-10 text-center text-sm text-slate-500">
            No exceptions available.
          </div>
        )}

      </div>

    </div>
  );
}


/* --------------------------------------------------
   TRANSACTION TABLE
-------------------------------------------------- */

function TransactionTable({
  transactions,
  onSelect,
}) {
  return (
    <div className="overflow-x-auto">

      <table className="w-full text-left text-sm">

        <thead className="border-b border-slate-800 text-xs uppercase text-slate-500">

          <tr>

            <th className="px-6 py-4">
              Transaction
            </th>

            <th className="px-6 py-4">
              Difference
            </th>

            <th className="px-6 py-4">
              Exception
            </th>

            <th className="px-6 py-4">
              Status
            </th>

            <th className="px-6 py-4">
              AI Confidence
            </th>

          </tr>

        </thead>


        <tbody>

          {transactions.map((tx) => (

            <tr
              key={tx.unified_transaction_id}
              onClick={() => onSelect?.(tx)}
              className={`border-b border-slate-800 last:border-0 ${
                onSelect
                  ? "cursor-pointer hover:bg-slate-800/40"
                  : ""
              }`}
            >

              <td className="px-6 py-4">

                <div>
                  <p className="font-medium">
                    {getTransactionLabel(tx)}
                  </p>

                  <p className="mt-1 text-xs text-slate-500">
                    {tx.unified_transaction_id}
                  </p>
                </div>

              </td>


              <td className="px-6 py-4">

                <span
                  className={
                    Number(tx.difference || 0) === 0
                      ? "text-emerald-400"
                      : "text-red-400"
                  }
                >
                  {formatDifference(tx.difference)}
                </span>

              </td>


              <td className="px-6 py-4 text-xs text-slate-400">
                {getExceptionLabel(tx)}
              </td>


              <td className="px-6 py-4">
                <StatusBadge status={tx.final_status} />
              </td>


              <td className="px-6 py-4 text-slate-300">
                {formatConfidence(tx.confidence_score)}
              </td>

            </tr>

          ))}

        </tbody>

      </table>

    </div>
  );
}


/* --------------------------------------------------
   RECONCILIATION
-------------------------------------------------- */

function Reconciliation({
  results,
  setSelected,
}) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("ALL");

  const filtered = useMemo(() => {

    return results.filter((tx) => {

      const searchText = (
        `${tx.unified_transaction_id || ""} ${
          tx.order_id || ""
        } ${tx.exception_type || ""}`
      ).toLowerCase();

      const matchesSearch =
        searchText.includes(search.toLowerCase());

      const matchesFilter =
        filter === "ALL" ||
        tx.final_status === filter;

      return matchesSearch && matchesFilter;

    });

  }, [results, search, filter]);


  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900">

      <div className="border-b border-slate-800 p-6">

        <h2 className="font-semibold">
          Reconciliation Results
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Review every transaction processed by the controller.
        </p>


        <div className="mt-5 flex flex-col gap-3 md:flex-row">

          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search transaction..."
            className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm outline-none focus:border-blue-500"
          />


          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm outline-none"
          >

            <option value="ALL">
              All statuses
            </option>

            <option value="RECONCILED">
              Reconciled
            </option>

            <option value="RESOLVED">
              Resolved
            </option>

            <option value="NEEDS_REVIEW">
              Needs Review
            </option>

            <option value="UNRESOLVED">
              Unresolved
            </option>

          </select>

        </div>

      </div>


      {filtered.length > 0 ? (

        <TransactionTable
          transactions={filtered}
          onSelect={setSelected}
        />

      ) : (

        <div className="px-6 py-12 text-center text-sm text-slate-500">
          No reconciliation results found.
        </div>

      )}

    </div>
  );
}


/* --------------------------------------------------
   EXCEPTIONS
-------------------------------------------------- */

function Exceptions({
  results,
  setSelected,
}) {
  const exceptions = results.filter(
    (tx) =>
      tx.final_status !== "RECONCILED"
  );

  const needsReview = results.filter(
    (tx) =>
      tx.final_status === "NEEDS_REVIEW"
  ).length;

  const unresolved = results.filter(
    (tx) =>
      tx.final_status === "UNRESOLVED"
  ).length;

  return (
    <div className="space-y-6">

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">

        <StatCard
          title="Open Exceptions"
          value={exceptions.length}
          subtitle="Across all sources"
          icon="!"
        />

        <StatCard
          title="Needs Review"
          value={needsReview}
          subtitle="Finance action required"
          icon="◉"
        />

        <StatCard
          title="Unresolved"
          value={unresolved}
          subtitle="Insufficient evidence"
          icon="○"
        />

      </div>


      <div className="rounded-2xl border border-slate-800 bg-slate-900">

        <div className="border-b border-slate-800 p-6">

          <h2 className="font-semibold">
            Exception Queue
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Investigate exceptions and review AI recommendations.
          </p>

        </div>


        {exceptions.length > 0 ? (

          <TransactionTable
            transactions={exceptions}
            onSelect={setSelected}
          />

        ) : (

          <div className="px-6 py-12 text-center text-sm text-slate-500">
            No exceptions available.
          </div>

        )}

      </div>

    </div>
  );
}


/* --------------------------------------------------
   ANALYTICS
-------------------------------------------------- */

function Analytics({
  results,
  summary,
}) {
  const exceptionDistribution = useMemo(() => {

    const counts = {};

    results.forEach((tx) => {

      if (tx.exception_type) {

        const name =
          tx.exception_type.replaceAll("_", " ");

        counts[name] =
          (counts[name] || 0) + 1;

      }

    });

    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1]);

  }, [results]);


  const maxException =
    exceptionDistribution.length > 0
      ? exceptionDistribution[0][1]
      : 1;


  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">

      {/* EXCEPTION DISTRIBUTION */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

        <h2 className="font-semibold">
          Exception Distribution
        </h2>

        <div className="mt-8 space-y-5">

          {exceptionDistribution.length > 0 ? (

            exceptionDistribution.map(
              ([name, value]) => (

                <div key={name}>

                  <div className="mb-2 flex justify-between text-sm">

                    <span className="text-slate-400">
                      {name}
                    </span>

                    <span>
                      {value}
                    </span>

                  </div>


                  <div className="h-2 rounded-full bg-slate-800">

                    <div
                      className="h-2 rounded-full bg-blue-500"
                      style={{
                        width: `${
                          (value / maxException) * 100
                        }%`,
                      }}
                    />

                  </div>

                </div>

              )
            )

          ) : (

            <p className="text-sm text-slate-500">
              No exception data available.
            </p>

          )}

        </div>

      </div>


      {/* CONTROLLER PERFORMANCE */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

        <h2 className="font-semibold">
          Controller Performance
        </h2>

        <div className="mt-8 grid grid-cols-2 gap-4">

          <div className="rounded-xl bg-slate-950 p-5">

            <p className="text-sm text-slate-500">
              Reconciliation Rate
            </p>

            <p className="mt-2 text-3xl font-semibold">

              {summary.total > 0
                ? `${(
                    (summary.reconciled /
                      summary.total) *
                    100
                  ).toFixed(2)}%`
                : "0.00%"}

            </p>

          </div>


          <div className="rounded-xl bg-slate-950 p-5">

            <p className="text-sm text-slate-500">
              AI Resolved
            </p>

            <p className="mt-2 text-3xl font-semibold">
              {summary.resolved}
            </p>

          </div>


          <div className="rounded-xl bg-slate-950 p-5">

            <p className="text-sm text-slate-500">
              Transactions
            </p>

            <p className="mt-2 text-3xl font-semibold">
              {summary.total}
            </p>

          </div>


          <div className="rounded-xl bg-slate-950 p-5">

            <p className="text-sm text-slate-500">
              Exceptions
            </p>

            <p className="mt-2 text-3xl font-semibold">

              {results.filter(
                (tx) =>
                  tx.final_status !==
                  "RECONCILED"
              ).length}

            </p>

          </div>

        </div>

      </div>

    </div>
  );
}


/* --------------------------------------------------
   AUDIT LOG
-------------------------------------------------- */

function AuditLog({
  summary,
}) {
  const events = [
    [
      "Current",
      "Reconciliation results",
      `${summary.total} transactions stored`,
    ],
    [
      "Current",
      "Reconciliation status",
      `${summary.reconciled} transactions reconciled`,
    ],
    [
      "Current",
      "AI decisions",
      `${summary.resolved} transactions AI resolved`,
    ],
    [
      "Current",
      "Review queue",
      `${summary.needs_review} transactions require review`,
    ],
    [
      "Current",
      "Unresolved cases",
      `${summary.unresolved} transactions unresolved`,
    ],
  ];

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900">

      <div className="border-b border-slate-800 p-6">

        <h2 className="font-semibold">
          Audit Log
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Controller activity and reconciliation events.
        </p>

      </div>


      <div className="divide-y divide-slate-800">

        {events.map(
          ([time, event, detail], index) => (

            <div
              key={`${event}-${index}`}
              className="flex gap-5 px-6 py-5"
            >

              <span className="font-mono text-xs text-slate-500">
                {time}
              </span>

              <div>

                <p className="text-sm font-medium">
                  {event}
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  {detail}
                </p>

              </div>

            </div>

          )
        )}

      </div>

    </div>
  );
}


/* --------------------------------------------------
   TRANSACTION DETAIL
-------------------------------------------------- */

function TransactionDetail({
  transaction,
  close,
}) {
  if (!transaction) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60">

      <div className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-800 bg-slate-950 p-6">

        {/* HEADER */}
        <div className="flex items-center justify-between">

          <div>

            <p className="text-xs text-slate-500">
              TRANSACTION
            </p>

            <h2 className="mt-1 text-xl font-semibold">
              {getTransactionLabel(transaction)}
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              {transaction.unified_transaction_id}
            </p>

          </div>


          <button
            onClick={close}
            className="rounded-lg bg-slate-800 px-3 py-2 text-slate-300 hover:bg-slate-700"
          >
            ✕
          </button>

        </div>


        {/* STATUS */}
        <div className="mt-6 flex items-center justify-between">

          <span className="text-sm text-slate-400">
            Status
          </span>

          <StatusBadge
            status={transaction.final_status}
          />

        </div>


        {/* FINANCIAL DIFFERENCE */}
        <div className="mt-6 rounded-xl border border-slate-800 bg-slate-900 p-5">

          <p className="text-xs text-slate-500">
            FINANCIAL DIFFERENCE
          </p>

          <p
            className={`mt-3 text-2xl font-semibold ${
              Number(transaction.difference || 0) === 0
                ? "text-emerald-400"
                : "text-red-400"
            }`}
          >
            {formatDifference(transaction.difference)}
          </p>

        </div>


        {/* EXCEPTION */}
        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900 p-5">

          <p className="text-xs text-slate-500">
            EXCEPTION
          </p>

          <p className="mt-2 font-medium">
            {getExceptionLabel(transaction)}
          </p>

        </div>


        {/* AI ANALYSIS */}
        <div className="mt-4 rounded-xl border border-blue-500/20 bg-blue-500/5 p-5">

          <div className="flex items-center gap-2">

            <span className="text-blue-400">
              ✦
            </span>

            <h3 className="font-medium">
              AI Analysis
            </h3>

          </div>


          <div className="mt-5">

            <p className="text-xs text-slate-500">
              EXPLANATION
            </p>

            <p className="mt-2 text-sm leading-6 text-slate-400">
              {transaction.ai_explanation ||
                "No AI explanation is available for this transaction."}
            </p>

          </div>


          <div className="mt-5">

            <p className="text-xs text-slate-500">
              AI CONFIDENCE
            </p>

            <p className="mt-1 text-xl font-semibold">
              {formatConfidence(
                transaction.confidence_score
              )}
            </p>

          </div>


          <div className="mt-5">

            <p className="text-xs text-slate-500">
              RECOMMENDED ACTION
            </p>

            <p className="mt-2 text-sm leading-6 text-slate-300">
              {transaction.recommended_action ||
                "No recommended action available."}
            </p>

          </div>


          {transaction.resolution && (
            <div className="mt-5">

              <p className="text-xs text-slate-500">
                RESOLUTION
              </p>

              <p className="mt-2 text-sm leading-6 text-slate-300">
                {transaction.resolution}
              </p>

            </div>
          )}


          <div className="mt-5">

            <p className="text-xs text-slate-500">
              HUMAN REVIEW
            </p>

            <p
              className={`mt-2 text-sm ${
                transaction.requires_human_review
                  ? "text-amber-400"
                  : "text-emerald-400"
              }`}
            >
              {transaction.requires_human_review
                ? "Human review required"
                : "No human review required"}
            </p>

          </div>

        </div>


        {/* ACTIONS */}
        <div className="mt-6 flex gap-3">

          <button
            className="flex-1 rounded-lg bg-blue-600 py-3 text-sm font-medium hover:bg-blue-500"
          >
            Mark Reviewed
          </button>

          <button
            className="rounded-lg border border-slate-700 px-5 py-3 text-sm hover:bg-slate-900"
          >
            Escalate
          </button>

        </div>

      </div>

    </div>
  );
}


/* --------------------------------------------------
   APP
-------------------------------------------------- */

function App() {

  const [page, setPage] =
    useState("Dashboard");

  const [selected, setSelected] =
    useState(null);

  const [summary, setSummary] =
    useState({
      total: 0,
      reconciled: 0,
      resolved: 0,
      needs_review: 0,
      unresolved: 0,
    });

  const [results, setResults] =
    useState([]);

  const [loading, setLoading] =
    useState(true);

  const [apiError, setApiError] =
    useState(null);


  /* --------------------------------------------------
     LOAD API DATA
  -------------------------------------------------- */

  const loadDashboardData = async () => {

    try {

      setLoading(true);
      setApiError(null);

      const [
        summaryResponse,
        resultsResponse,
      ] = await Promise.all([

        fetch(
          `${API_BASE_URL}/summary`
        ),

        fetch(
          `${API_BASE_URL}/results`
        ),

      ]);


      if (
        !summaryResponse.ok ||
        !resultsResponse.ok
      ) {
        throw new Error(
          "Failed to load reconciliation data"
        );
      }


      const summaryData =
        await summaryResponse.json();

      const resultsData =
        await resultsResponse.json();


      setSummary({
        total: summaryData.total || 0,
        reconciled:
          summaryData.reconciled || 0,
        resolved:
          summaryData.resolved || 0,
        needs_review:
          summaryData.needs_review || 0,
        unresolved:
          summaryData.unresolved || 0,
      });


      setResults(
        Array.isArray(resultsData)
          ? resultsData
          : []
      );

    } catch (error) {

      console.error(
        "API Error:",
        error
      );

      setApiError(
        error.message ||
        "Unable to connect to API"
      );

    } finally {

      setLoading(false);

    }

  };


  /* --------------------------------------------------
     INITIAL LOAD
  -------------------------------------------------- */

  useEffect(() => {
    loadDashboardData();
  }, []);


  /* --------------------------------------------------
     PAGE RENDER
  -------------------------------------------------- */

  const renderPage = () => {

    switch (page) {

      case "Reconciliation":

        return (
          <Reconciliation
            results={results}
            setSelected={setSelected}
          />
        );


      case "Exceptions":

        return (
          <Exceptions
            results={results}
            setSelected={setSelected}
          />
        );


      case "Analytics":

        return (
          <Analytics
            results={results}
            summary={summary}
          />
        );


      case "Audit Log":

        return (
          <AuditLog
            summary={summary}
          />
        );


      default:

        return (
          <Dashboard
            summary={summary}
            results={results}
            setPage={setPage}
            loading={loading}
          />
        );

    }

  };


  return (
    <div className="min-h-screen bg-slate-950 text-white">

      {/* --------------------------------------------------
          SIDEBAR
      -------------------------------------------------- */}

      <aside className="fixed left-0 top-0 z-40 hidden h-screen w-64 border-r border-slate-800 bg-slate-900 lg:block">

        <div className="p-6">

          <div className="text-xl font-bold">
            AI Finance
          </div>

          <div className="text-xl font-bold text-blue-400">
            Controller
          </div>

          <p className="mt-2 text-xs text-slate-500">
            Intelligent Reconciliation
          </p>

        </div>


        <nav className="px-4">

          {navItems.map((item) => (

            <button
              key={item.name}
              onClick={() =>
                setPage(item.name)
              }
              className={`mb-1 flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm transition ${
                page === item.name
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              }`}
            >

              <span className="w-5 text-center">
                {item.icon}
              </span>

              {item.name}

            </button>

          ))}

        </nav>


        <div className="absolute bottom-6 left-5 right-5 rounded-xl border border-slate-800 bg-slate-950 p-4">

          <div className="flex items-center gap-2">

            <span
              className={`h-2 w-2 rounded-full ${
                apiError
                  ? "bg-red-400"
                  : "bg-emerald-400"
              }`}
            />

            <span className="text-xs text-slate-400">

              {apiError
                ? "API connection error"
                : "System operational"}

            </span>

          </div>

        </div>

      </aside>


      {/* --------------------------------------------------
          MAIN
      -------------------------------------------------- */}

      <main className="lg:ml-64">


        {/* HEADER */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-800 bg-slate-950/90 px-6 py-5 backdrop-blur md:px-8">

          <div>

            <h1 className="text-xl font-semibold">
              {page}
            </h1>

            <p className="mt-1 text-xs text-slate-500">
              AI-powered multi-source payment reconciliation
            </p>

          </div>


          <button
            disabled
            title="Temporarily disabled while Gemini quota is being managed"
            className="cursor-not-allowed rounded-lg bg-blue-600/50 px-4 py-2.5 text-sm font-medium opacity-70"
          >
            + Run Reconciliation
          </button>

        </header>


        {/* --------------------------------------------------
            API ERROR
        -------------------------------------------------- */}

        {apiError && (

          <div className="mx-5 mt-5 rounded-xl border border-red-500/20 bg-red-500/5 px-5 py-4 md:mx-8">

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">

              <div>

                <p className="text-sm font-medium text-red-400">
                  Unable to load backend data
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  {apiError}
                </p>

              </div>


              <button
                onClick={loadDashboardData}
                className="rounded-lg border border-slate-700 px-4 py-2 text-xs hover:bg-slate-800"
              >
                Retry
              </button>

            </div>

          </div>

        )}


        {/* MOBILE NAV */}
        <div className="flex gap-2 overflow-x-auto border-b border-slate-800 bg-slate-900 px-4 py-3 lg:hidden">

          {navItems.map((item) => (

            <button
              key={item.name}
              onClick={() =>
                setPage(item.name)
              }
              className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs ${
                page === item.name
                  ? "bg-blue-600"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              {item.name}
            </button>

          ))}

        </div>


        {/* CONTENT */}
        <section className="p-5 md:p-8">

          {loading ? (

            <div className="flex min-h-[400px] items-center justify-center">

              <div className="text-center">

                <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-blue-500" />

                <p className="mt-4 text-sm text-slate-500">
                  Loading reconciliation data...
                </p>

              </div>

            </div>

          ) : (

            renderPage()

          )}

        </section>

      </main>


      {/* TRANSACTION DETAIL */}

      {selected && (

        <TransactionDetail
          transaction={selected}
          close={() =>
            setSelected(null)
          }
        />

      )}

    </div>
  );
}

export default App;