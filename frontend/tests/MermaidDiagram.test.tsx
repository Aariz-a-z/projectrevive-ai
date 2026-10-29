/**
 * What happens when a diagram will not draw.
 *
 * README section 4.6 asks for useful error handling when rendering fails, and
 * this is the path nobody exercises by hand: the backend refuses to emit a
 * diagram it cannot parse back, so in practice it always renders. A blank
 * panel would be the worst outcome — a reader could not tell a project with
 * no architecture from a broken page.
 */

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MermaidDiagram } from "@/components/MermaidDiagram";

const mermaidMock = {
  initialize: vi.fn(),
  render: vi.fn(),
};

vi.mock("mermaid", () => ({ default: mermaidMock }));

const CHART = 'flowchart TD\n    Data[("Dataset")]\n    Data --> Model';

describe("when it renders", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mermaidMock.render.mockResolvedValue({ svg: "<svg><title>diagram</title></svg>" });
  });

  it("shows the diagram with an accessible name", async () => {
    render(<MermaidDiagram chart={CHART} ariaLabel="Current architecture" />);

    expect(
      await screen.findByRole("img", { name: "Current architecture" }),
    ).toBeInTheDocument();
  });

  it("keeps the source available without showing an error", async () => {
    render(<MermaidDiagram chart={CHART} ariaLabel="Current architecture" />);
    await screen.findByRole("img", { name: "Current architecture" });

    expect(screen.getByText("Show diagram source")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders the chart it was given", async () => {
    render(<MermaidDiagram chart={CHART} ariaLabel="Current architecture" />);
    await screen.findByRole("img", { name: "Current architecture" });

    expect(mermaidMock.render).toHaveBeenCalledWith(
      expect.any(String),
      CHART,
    );
  });

  it("uses a DOM-safe id, since React's contains colons", async () => {
    render(<MermaidDiagram chart={CHART} ariaLabel="Current architecture" />);
    await screen.findByRole("img", { name: "Current architecture" });

    const [id] = mermaidMock.render.mock.calls[0];
    expect(id).toMatch(/^mermaid-[a-zA-Z0-9]+$/);
  });
});

describe("when it fails", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mermaidMock.render.mockRejectedValue(new Error("Parse error on line 2"));
  });

  it("says so instead of showing a blank panel", async () => {
    render(<MermaidDiagram chart={CHART} ariaLabel="Current architecture" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /could not be drawn/i,
    );
  });

  it("surfaces the actual error rather than a generic apology", async () => {
    render(<MermaidDiagram chart={CHART} ariaLabel="Current architecture" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Parse error on line 2",
    );
  });

  it("still shows the source, which is useful on its own", async () => {
    render(<MermaidDiagram chart={CHART} ariaLabel="Current architecture" />);
    await screen.findByRole("alert");

    expect(screen.getByText(/flowchart TD/)).toBeInTheDocument();
  });

  it("does not claim to be an image when there is no image", async () => {
    render(<MermaidDiagram chart={CHART} ariaLabel="Current architecture" />);
    await screen.findByRole("alert");

    expect(
      screen.queryByRole("img", { name: "Current architecture" }),
    ).not.toBeInTheDocument();
  });
});
