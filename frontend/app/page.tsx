"use client";

import { useEffect, useState, useTransition } from "react";
import {
  allocateEqualShares,
  formatSatangToAmount,
  formatSatangToDisplay,
  parseAmountToSatang,
} from "./lib/money";

interface Group {
  id: number;
  name: string;
  members: string[];
}

interface ExpenseShare {
  username: string;
  amount: string;
}

interface Expense {
  id: number;
  group_id: number;
  description: string;
  paid_by: string;
  amount: string;
  created_at: string;
  deleted_at: string | null;
  shares: ExpenseShare[];
}

interface Balance {
  username: string;
  balance: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ALL_USERS = ["alice", "bob", "carol", "dan"];

export default function SplitBillPage() {
  const [currentUser, setCurrentUser] = useState("alice");
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);

  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [balances, setBalances] = useState<Balance[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Expense form state
  const [description, setDescription] = useState("");
  const [amountStr, setAmountStr] = useState("");
  const [paidBy, setPaidBy] = useState("alice");
  const [splitType, setSplitType] = useState<"equal" | "exact">("equal");
  const [equalMembers, setEqualMembers] = useState<string[]>([]);
  const [exactShares, setExactShares] = useState<Record<string, string>>({});
  const [idempotencyKey, setIdempotencyKey] = useState<string>(() => crypto.randomUUID());

  const [isPending, startTransition] = useTransition();

  // Load groups when currentUser changes
  useEffect(() => {
    setErrorMessage(null);
    fetch(`${API_BASE}/groups`, {
      headers: { "X-User": currentUser },
    })
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail?.message || "Failed to load groups");
        }
        return res.json();
      })
      .then((data: Group[]) => {
        setGroups(data);
        if (data.length > 0) {
          setSelectedGroupId(data[0].id);
        } else {
          setSelectedGroupId(null);
          setSelectedGroup(null);
          setExpenses([]);
          setBalances([]);
        }
      })
      .catch((err) => {
        setErrorMessage(err.message);
      });
  }, [currentUser]);

  // Load group details, expenses, and balances when selectedGroupId or currentUser changes
  useEffect(() => {
    if (!selectedGroupId) return;
    setErrorMessage(null);

    // Fetch group details
    fetch(`${API_BASE}/groups/${selectedGroupId}`, {
      headers: { "X-User": currentUser },
    })
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail?.message || "Failed to load group details");
        }
        return res.json();
      })
      .then((group: Group) => {
        setSelectedGroup(group);
        setPaidBy(currentUser);
        setEqualMembers(group.members);
        const initialExact: Record<string, string> = {};
        group.members.forEach((m) => {
          initialExact[m] = "";
        });
        setExactShares(initialExact);
      })
      .catch((err) => setErrorMessage(err.message));

    // Fetch expenses
    fetch(`${API_BASE}/groups/${selectedGroupId}/expenses`, {
      headers: { "X-User": currentUser },
    })
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail?.message || "Failed to load expenses");
        }
        return res.json();
      })
      .then((data: Expense[]) => setExpenses(data))
      .catch((err) => setErrorMessage(err.message));

    // Fetch balances
    fetch(`${API_BASE}/groups/${selectedGroupId}/balances`, {
      headers: { "X-User": currentUser },
    })
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail?.message || "Failed to load balances");
        }
        return res.json();
      })
      .then((data) => setBalances(data.balances))
      .catch((err) => setErrorMessage(err.message));
  }, [selectedGroupId, currentUser]);

  // Regenerate idempotency key when form inputs change
  const handleInputChange = () => {
    setIdempotencyKey(crypto.randomUUID());
  };

  // Live preview calculation
  let parsedSatang = 0;
  let isAmountValid = false;
  try {
    parsedSatang = parseAmountToSatang(amountStr);
    isAmountValid = true;
  } catch {
    isAmountValid = false;
  }

  // Calculate live preview and unallocated satang for exact split
  let livePreview: { username: string; satang: number; amount: string }[] = [];
  let unallocatedSatang = 0;

  if (isAmountValid && selectedGroup) {
    if (splitType === "equal") {
      // Order strictly according to group.members
      const orderedSelected = selectedGroup.members.filter((m) =>
        equalMembers.includes(m)
      );
      livePreview = allocateEqualShares(parsedSatang, orderedSelected);
    } else {
      let allocatedTotal = 0;
      livePreview = selectedGroup.members.map((m) => {
        let s = 0;
        try {
          s = parseAmountToSatang(exactShares[m] || "0", true);
        } catch {
          s = 0;
        }
        allocatedTotal += s;
        return {
          username: m,
          satang: s,
          amount: formatSatangToAmount(s),
        };
      });
      unallocatedSatang = parsedSatang - allocatedTotal;
    }
  }

  const isFormValid =
    description.trim().length > 0 &&
    description.trim().length <= 200 &&
    isAmountValid &&
    (splitType === "equal" ? equalMembers.length > 0 : unallocatedSatang === 0);

  // Submit expense handler
  const handleCreateExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isFormValid || !selectedGroupId || !selectedGroup) return;

    setErrorMessage(null);

    const payload = {
      description: description.trim(),
      paid_by: paidBy,
      amount: formatSatangToAmount(parsedSatang),
      split:
        splitType === "equal"
          ? {
              type: "equal",
              members: selectedGroup.members.filter((m) =>
                equalMembers.includes(m)
              ),
            }
          : {
              type: "exact",
              shares: Object.fromEntries(
                selectedGroup.members.map((m) => [
                  m,
                  formatSatangToAmount(
                    parseAmountToSatang(exactShares[m] || "0", true)
                  ),
                ])
              ),
            },
    };

    startTransition(async () => {
      try {
        const res = await fetch(`${API_BASE}/groups/${selectedGroupId}/expenses`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-User": currentUser,
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail?.message || "Failed to create expense");
        }

        // Successfully created or replayed
        setDescription("");
        setAmountStr("");
        setIdempotencyKey(crypto.randomUUID());

        // Refresh expenses and balances
        const [expRes, balRes] = await Promise.all([
          fetch(`${API_BASE}/groups/${selectedGroupId}/expenses`, {
            headers: { "X-User": currentUser },
          }),
          fetch(`${API_BASE}/groups/${selectedGroupId}/balances`, {
            headers: { "X-User": currentUser },
          }),
        ]);
        if (expRes.ok) setExpenses(await expRes.json());
        if (balRes.ok) setBalances((await balRes.json()).balances);
      } catch (err: unknown) {
        if (err instanceof Error) {
          setErrorMessage(err.message);
        } else {
          setErrorMessage("An unexpected error occurred");
        }
      }
    });
  };

  // Delete expense handler
  const handleDeleteExpense = async (expenseId: number) => {
    if (!selectedGroupId) return;
    setErrorMessage(null);
    try {
      const res = await fetch(
        `${API_BASE}/groups/${selectedGroupId}/expenses/${expenseId}`,
        {
          method: "DELETE",
          headers: { "X-User": currentUser },
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.message || "Failed to delete expense");
      }

      // Refresh list and balances
      const [expRes, balRes] = await Promise.all([
        fetch(`${API_BASE}/groups/${selectedGroupId}/expenses`, {
          headers: { "X-User": currentUser },
        }),
        fetch(`${API_BASE}/groups/${selectedGroupId}/balances`, {
          headers: { "X-User": currentUser },
        }),
      ]);
      if (expRes.ok) setExpenses(await expRes.json());
      if (balRes.ok) setBalances((await balRes.json()).balances);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      }
    }
  };

  return (
    <main className="mx-auto max-w-5xl p-6 font-sans">
      <header className="flex flex-wrap items-center justify-between border-b pb-4 gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">SplitBill</h1>
          <p className="text-sm text-slate-500">Shared expense manager</p>
        </div>

        {/* User selector */}
        <div className="flex items-center gap-2">
          <label htmlFor="user-select" className="text-sm font-medium text-slate-700">
            Active User (X-User):
          </label>
          <select
            id="user-select"
            value={currentUser}
            onChange={(e) => setCurrentUser(e.target.value)}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm font-semibold"
          >
            {ALL_USERS.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Global Error message */}
      {errorMessage && (
        <div className="mt-4 rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <p className="font-semibold">Error</p>
          <p>{errorMessage}</p>
        </div>
      )}

      {/* Group Selector */}
      <section className="mt-6">
        <label htmlFor="group-select" className="block text-sm font-medium text-slate-700">
          Select Group:
        </label>
        {groups.length === 0 ? (
          <p className="mt-1 text-sm text-slate-500">No groups available for {currentUser}.</p>
        ) : (
          <div className="mt-2 flex gap-2">
            {groups.map((g) => (
              <button
                key={g.id}
                onClick={() => setSelectedGroupId(g.id)}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                  selectedGroupId === g.id
                    ? "bg-slate-900 text-white shadow"
                    : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                {g.name}
              </button>
            ))}
          </div>
        )}
      </section>

      {selectedGroup && (
        <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-3">
          {/* Left Column: Form & Preview */}
          <div className="lg:col-span-2 space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold mb-4">Add Expense</h2>
              <form onSubmit={handleCreateExpense} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase">
                    Description
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={200}
                    value={description}
                    onChange={(e) => {
                      setDescription(e.target.value);
                      handleInputChange();
                    }}
                    placeholder="e.g. Dinner at Night Market"
                    className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 uppercase">
                      Amount (THB)
                    </label>
                    <input
                      type="text"
                      required
                      value={amountStr}
                      onChange={(e) => {
                        setAmountStr(e.target.value);
                        handleInputChange();
                      }}
                      placeholder="e.g. 1,000.00"
                      className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 uppercase">
                      Paid By
                    </label>
                    <select
                      value={paidBy}
                      onChange={(e) => {
                        setPaidBy(e.target.value);
                        handleInputChange();
                      }}
                      className="mt-1 block w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm"
                    >
                      {selectedGroup.members.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase mb-2">
                    Split Type
                  </label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="splitType"
                        value="equal"
                        checked={splitType === "equal"}
                        onChange={() => {
                          setSplitType("equal");
                          handleInputChange();
                        }}
                      />
                      Equal Split
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="splitType"
                        value="exact"
                        checked={splitType === "exact"}
                        onChange={() => {
                          setSplitType("exact");
                          handleInputChange();
                        }}
                      />
                      Exact Amounts
                    </label>
                  </div>
                </div>

                {/* Split Configuration */}
                {splitType === "equal" ? (
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">
                      Include Members
                    </label>
                    <div className="flex flex-wrap gap-3">
                      {selectedGroup.members.map((m) => (
                        <label key={m} className="flex items-center gap-1.5 text-sm">
                          <input
                            type="checkbox"
                            checked={equalMembers.includes(m)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setEqualMembers([...equalMembers, m]);
                              } else {
                                setEqualMembers(equalMembers.filter((u) => u !== m));
                              }
                              handleInputChange();
                            }}
                          />
                          {m}
                        </label>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 uppercase mb-2">
                      Exact Shares per Member
                    </label>
                    <div className="space-y-2">
                      {selectedGroup.members.map((m) => (
                        <div key={m} className="flex items-center gap-3">
                          <span className="w-20 text-sm font-medium">{m}:</span>
                          <input
                            type="text"
                            placeholder="0.00"
                            value={exactShares[m] || ""}
                            onChange={(e) => {
                              setExactShares({ ...exactShares, [m]: e.target.value });
                              handleInputChange();
                            }}
                            className="w-36 rounded border border-slate-300 px-2 py-1 text-sm"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Live Preview Box */}
                {isAmountValid && (
                  <div className="rounded border border-slate-200 bg-slate-50 p-4 text-sm space-y-2">
                    <p className="font-semibold text-slate-800">Live Allocation Preview:</p>
                    <div className="divide-y divide-slate-200">
                      {livePreview.map((item) => (
                        <div key={item.username} className="flex justify-between py-1">
                          <span>{item.username}</span>
                          <span className="font-mono">฿{formatSatangToDisplay(item.satang)}</span>
                        </div>
                      ))}
                    </div>
                    {splitType === "exact" && (
                      <div className="mt-2 pt-2 border-t flex justify-between font-medium">
                        <span>Unallocated remainder:</span>
                        <span
                          className={`font-mono ${
                            unallocatedSatang === 0 ? "text-emerald-600" : "text-rose-600"
                          }`}
                        >
                          ฿{formatSatangToDisplay(unallocatedSatang)}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={!isFormValid || isPending}
                  className="w-full rounded bg-slate-900 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
                >
                  {isPending ? "Submitting..." : "Record Expense"}
                </button>
              </form>
            </div>

            {/* Expense List */}
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold mb-4">Expenses</h2>
              {expenses.length === 0 ? (
                <p className="text-sm text-slate-500">No expenses recorded yet.</p>
              ) : (
                <div className="divide-y divide-slate-100">
                  {expenses.map((exp) => (
                    <div key={exp.id} className="py-4 flex justify-between items-start gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-semibold text-slate-900">{exp.description}</p>
                          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                            Paid by {exp.paid_by}
                          </span>
                        </div>
                        <p className="text-sm font-mono text-slate-700 mt-1">
                          Total: ฿{formatSatangToDisplay(parseAmountToSatang(exp.amount))}
                        </p>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {exp.shares.map((s) => (
                            <span
                              key={s.username}
                              className="text-xs bg-slate-50 border border-slate-200 rounded px-2 py-0.5"
                            >
                              {s.username}: ฿{formatSatangToDisplay(parseAmountToSatang(s.amount, true))}
                            </span>
                          ))}
                        </div>
                      </div>

                      {exp.paid_by === currentUser && (
                        <button
                          onClick={() => handleDeleteExpense(exp.id)}
                          className="text-xs text-rose-600 hover:text-rose-800 border border-rose-200 hover:border-rose-300 rounded px-2 py-1"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Balances */}
          <div>
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm sticky top-6">
              <h2 className="text-xl font-semibold mb-4">Group Balances</h2>
              <div className="divide-y divide-slate-100">
                {balances.map((b) => {
                  const satang = parseAmountToSatang(b.balance, true);
                  const isPositive = satang > 0;
                  const isNegative = satang < 0;
                  return (
                    <div key={b.username} className="py-3 flex justify-between items-center">
                      <span className="font-medium text-slate-800">{b.username}</span>
                      <span
                        className={`font-mono text-sm font-semibold ${
                          isPositive
                            ? "text-emerald-600"
                            : isNegative
                            ? "text-rose-600"
                            : "text-slate-500"
                        }`}
                      >
                        {isPositive ? "+" : ""}
                        ฿{formatSatangToDisplay(satang)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
