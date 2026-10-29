/**
 * The ARIA tabs pattern.
 *
 * `role="tab"` alone is easy and misleading: a screen reader announces "tab,
 * 3 of 9" while nothing connects a tab to its content, and reaching that
 * content takes nine Tab presses. These assert the parts that make it work
 * rather than merely look correct.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { TabList, TabPanel, type TabSpec } from "@/components/Tabs";

const TABS: readonly TabSpec<"one" | "two" | "three">[] = [
  { id: "one", label: "One" },
  { id: "two", label: "Two" },
  { id: "three", label: "Three" },
];

function Harness() {
  const [active, setActive] = useState<"one" | "two" | "three">("one");
  return (
    <>
      <TabList
        tabs={TABS}
        active={active}
        onChange={setActive}
        label="Sections"
        idPrefix="t"
      />
      <TabPanel id={active} idPrefix="t" active>
        <p>Panel for {active}</p>
      </TabPanel>
    </>
  );
}

describe("structure", () => {
  it("labels the tablist", () => {
    render(<Harness />);
    expect(screen.getByRole("tablist", { name: "Sections" })).toBeInTheDocument();
  });

  it("marks exactly one tab selected", () => {
    render(<Harness />);
    const selected = screen
      .getAllByRole("tab")
      .filter((t) => t.getAttribute("aria-selected") === "true");
    expect(selected).toHaveLength(1);
    expect(selected[0]).toHaveTextContent("One");
  });

  it("keeps exactly one tab in the tab order", () => {
    render(<Harness />);
    const inOrder = screen
      .getAllByRole("tab")
      .filter((t) => t.getAttribute("tabindex") === "0");
    expect(inOrder).toHaveLength(1);
  });

  it("ties the selected tab to the rendered panel", () => {
    render(<Harness />);
    const tab = screen.getByRole("tab", { selected: true });
    const panel = screen.getByRole("tabpanel");

    expect(tab.getAttribute("aria-controls")).toBe(panel.id);
    expect(panel.getAttribute("aria-labelledby")).toBe(tab.id);
  });

  it("does not point unselected tabs at panels that do not exist", () => {
    render(<Harness />);
    const unselected = screen
      .getAllByRole("tab")
      .filter((t) => t.getAttribute("aria-selected") === "false");

    expect(unselected).not.toHaveLength(0);
    for (const tab of unselected) {
      expect(tab.getAttribute("aria-controls")).toBeNull();
    }
  });
});

describe("keyboard", () => {
  it("moves right with ArrowRight and focus follows", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    screen.getByRole("tab", { name: "One" }).focus();
    await user.keyboard("{ArrowRight}");

    const now = screen.getByRole("tab", { selected: true });
    expect(now).toHaveTextContent("Two");
    expect(now).toHaveFocus();
  });

  it("moves left with ArrowLeft", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    screen.getByRole("tab", { name: "One" }).focus();
    await user.keyboard("{ArrowRight}{ArrowLeft}");

    expect(screen.getByRole("tab", { selected: true })).toHaveTextContent("One");
  });

  it("wraps around at both ends", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    screen.getByRole("tab", { name: "One" }).focus();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { selected: true })).toHaveTextContent("Three");

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { selected: true })).toHaveTextContent("One");
  });

  it("jumps to the first and last tab with Home and End", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    screen.getByRole("tab", { name: "One" }).focus();
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { selected: true })).toHaveTextContent("Three");

    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { selected: true })).toHaveTextContent("One");
  });

  it("leaves other keys alone so typing and Tab still work", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    screen.getByRole("tab", { name: "One" }).focus();
    await user.keyboard("a{ArrowDown}");

    expect(screen.getByRole("tab", { selected: true })).toHaveTextContent("One");
  });

  it("updates the panel when the selection moves", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    screen.getByRole("tab", { name: "One" }).focus();
    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("tabpanel")).toHaveTextContent("Panel for two");
  });
});

describe("pointer", () => {
  it("selects a tab on click", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("tab", { name: "Three" }));

    expect(screen.getByRole("tab", { selected: true })).toHaveTextContent("Three");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Panel for three");
  });
});
