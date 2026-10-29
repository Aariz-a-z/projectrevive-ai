"use client";

/**
 * The ARIA tabs pattern, properly.
 *
 * `role="tab"` on a button is the easy part and on its own it is misleading:
 * a screen reader announces "tab, 3 of 9" while nothing connects the tab to
 * the content it controls, and the keyboard behaviour is wrong. The APG
 * pattern needs three more things, all implemented here:
 *
 * - `aria-controls` / `aria-labelledby` tying each tab to its panel, so the
 *   relationship is announced and the panel is reachable.
 * - A roving tabindex: exactly one tab is in the tab order. Without it,
 *   reaching the content below means pressing Tab nine times.
 * - Arrow, Home and End keys to move between tabs, which is what someone
 *   using a keyboard will actually try.
 */

import { useRef, type KeyboardEvent, type ReactNode } from "react";

export interface TabSpec<Id extends string> {
  id: Id;
  label: string;
  icon?: ReactNode;
}

export function TabList<Id extends string>({
  tabs,
  active,
  onChange,
  label,
  idPrefix,
}: {
  tabs: readonly TabSpec<Id>[];
  active: Id;
  onChange: (id: Id) => void;
  label: string;
  idPrefix: string;
}) {
  const refs = useRef(new Map<Id, HTMLButtonElement>());

  function move(to: number) {
    const index = (to + tabs.length) % tabs.length;
    const next = tabs[index].id;
    onChange(next);
    // Focus follows selection, which is what "automatic activation" means in
    // the APG pattern and what makes arrow keys feel like one movement.
    refs.current.get(next)?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const current = tabs.findIndex((t) => t.id === active);
    switch (event.key) {
      case "ArrowRight":
        move(current + 1);
        break;
      case "ArrowLeft":
        move(current - 1);
        break;
      case "Home":
        move(0);
        break;
      case "End":
        move(tabs.length - 1);
        break;
      default:
        return;
    }
    // Only prevented for keys actually handled, so Tab and typing still work.
    event.preventDefault();
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className="flex flex-wrap gap-1 rounded-xl border border-edge bg-panel-inset p-1"
    >
      {tabs.map((tab) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            ref={(node) => {
              if (node) refs.current.set(tab.id, node);
              else refs.current.delete(tab.id);
            }}
            role="tab"
            id={`${idPrefix}-tab-${tab.id}`}
            aria-selected={selected}
            // Only the selected tab's panel is rendered, so only its
            // reference resolves. Pointing the others at ids that do not
            // exist would be a broken relationship announced as a real one.
            aria-controls={selected ? `${idPrefix}-panel-${tab.id}` : undefined}
            // Roving tabindex: one stop for the whole tablist.
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm transition-colors ${
              selected
                ? "bg-panel-raised font-medium text-fg shadow-sm ring-1 ring-edge-bright"
                : "text-muted hover:text-fg-dim"
            }`}
          >
            {tab.icon && (
              <span aria-hidden="true" className={`h-4 w-4 ${selected ? "text-cyan" : ""}`}>
                {tab.icon}
              </span>
            )}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({
  id,
  idPrefix,
  active,
  children,
}: {
  id: string;
  idPrefix: string;
  active: boolean;
  children: ReactNode;
}) {
  if (!active) return null;
  return (
    <div
      role="tabpanel"
      id={`${idPrefix}-panel-${id}`}
      aria-labelledby={`${idPrefix}-tab-${id}`}
      // Focusable so a keyboard user can move from the tab into the panel
      // content; -1 keeps it out of the normal tab sequence.
      tabIndex={0}
      className="focus-visible:outline-cyan"
    >
      {children}
    </div>
  );
}
