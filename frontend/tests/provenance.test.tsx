/**
 * How evidence and its absence are shown.
 *
 * This is the product's central claim rendered as pixels: a reader must be
 * able to tell what the report said from what the system guessed, and a rule
 * that can be checked from a model judgement that cannot. A regression here
 * would not throw — it would quietly present an inference as a fact, which is
 * the one failure this project exists to avoid.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ClaimChips, ClaimView } from "@/components/ClaimView";
import { FindingCard } from "@/components/FindingCard";
import type { Claim, Finding } from "@/lib/types";

const stated: Claim = {
  value: "CNN",
  source: "stated",
  evidence: [{ page: 3, quote: "We implemented a CNN in Python." }],
  reasoning: null,
};

const inferred: Claim = {
  value: "computer vision",
  source: "inferred",
  evidence: [],
  reasoning: "Several vision keywords appear in the document.",
};

function finding(overrides: Partial<Finding> = {}): Finding {
  return {
    title: "Evaluated on a single train/test split",
    category: "evaluation",
    kind: "weakness",
    severity: "high",
    explanation: "A single split makes the score depend on which rows landed where.",
    evidence: [{ page: 4, quote: "accuracy of 98.2 percent on the test split." }],
    searched_for: null,
    detected_by: "rule",
    rule_id: "single-split-only",
    ...overrides,
  };
}

describe("claims", () => {
  it("labels a stated claim as coming from the report", () => {
    render(<ClaimView claim={stated} />);
    expect(screen.getByText("In report")).toBeInTheDocument();
    expect(screen.queryByText("Inferred")).not.toBeInTheDocument();
  });

  it("labels an inferred claim as inferred", () => {
    render(<ClaimView claim={inferred} />);
    expect(screen.getByText("Inferred")).toBeInTheDocument();
    expect(screen.queryByText("In report")).not.toBeInTheDocument();
  });

  it("shows the reasoning behind an inference", () => {
    render(<ClaimView claim={inferred} />);
    expect(
      screen.getByText(/Several vision keywords appear/),
    ).toBeInTheDocument();
  });

  it("keeps the quote one click away rather than hidden", async () => {
    const user = userEvent.setup();
    render(<ClaimView claim={stated} />);

    expect(screen.getByText(/Show evidence/)).toBeInTheDocument();
    await user.click(screen.getByText(/Show evidence/));

    expect(screen.getByText(/We implemented a CNN in Python/)).toBeVisible();
    expect(screen.getByText("page 3")).toBeVisible();
  });

  it("offers no evidence control for an inference, which has none", () => {
    render(<ClaimView claim={inferred} />);
    expect(screen.queryByText(/Show evidence/)).not.toBeInTheDocument();
  });

  it("puts the page number on a stated chip", () => {
    render(<ClaimChips claims={[stated]} />);
    expect(screen.getByText("p3")).toBeInTheDocument();
  });

  it("says so plainly when nothing was identified", () => {
    render(<ClaimChips claims={[]} />);
    expect(screen.getByText("None identified")).toBeInTheDocument();
  });
});

describe("findings", () => {
  it("distinguishes something present from something missing", () => {
    const { unmount } = render(<FindingCard finding={finding()} />);
    expect(screen.getByText("Present")).toBeInTheDocument();
    unmount();

    render(
      <FindingCard
        finding={finding({
          kind: "gap",
          evidence: [],
          searched_for: "Searched for: pytest, unittest",
        })}
      />,
    );
    expect(screen.getByText("Missing")).toBeInTheDocument();
  });

  it("distinguishes a checkable rule from a model judgement", () => {
    const { unmount } = render(<FindingCard finding={finding()} />);
    expect(screen.getByText("Rule")).toBeInTheDocument();
    unmount();

    render(
      <FindingCard
        finding={finding({ detected_by: "model", rule_id: null })}
      />,
    );
    expect(screen.getByText("Model")).toBeInTheDocument();
  });

  it("shows the quote a weakness objects to, with its page", () => {
    render(<FindingCard finding={finding()} />);
    expect(screen.getByText(/98.2 percent on the test split/)).toBeInTheDocument();
    expect(screen.getByText("page 4")).toBeInTheDocument();
  });

  it("shows what was searched for on a gap, since absence cannot be quoted", () => {
    render(
      <FindingCard
        finding={finding({
          kind: "gap",
          evidence: [],
          searched_for: "Searched the report for: pytest, unittest",
        })}
      />,
    );
    expect(screen.getByText(/Searched the report for/)).toBeInTheDocument();
  });

  it("states severity in words, not colour alone", () => {
    render(<FindingCard finding={finding({ severity: "high" })} />);
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("names the rule so a reader can go and read it", () => {
    render(<FindingCard finding={finding()} />);
    expect(screen.getByText(/single-split-only/)).toBeInTheDocument();
  });
});
