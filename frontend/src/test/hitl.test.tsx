// Tests required by Prompt A5:
// 1. Approve / Save edits / Reject render and enable when awaiting_review.
// 2. Disclaimer banner contains "Not for clinical use".
// 3. Run assistant is disabled with empty input.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HitlDrawer from "../components/HitlDrawer";
import Disclaimer from "../components/Disclaimer";
import Workspace from "../pages/Workspace";
import type { RunRecord } from "../types";

vi.mock("../api", () => ({
  submitReview: vi.fn().mockResolvedValue({ run_id: "run-x", status: "finalized" }),
  getCases: vi.fn().mockResolvedValue([]),
  getRun: vi.fn().mockResolvedValue(null),
  startRun: vi.fn(),
  subscribeRunEvents: vi.fn().mockReturnValue(() => {}),
  sendChat: vi.fn(),
}));

import { submitReview } from "../api";

function makeRun(overrides: Partial<RunRecord> = {}): RunRecord {
  return {
    run_id: "run-test-1",
    case_id: "CR-001",
    status: "awaiting_review",
    summary: "Mock draft summary. Educational prototype. Not for clinical use.",
    recommendations: [{ title: "Discuss intensification", detail: "Teaching only.", citations: ["Card"] }],
    lab_flags: [{ analyte: "HbA1c", value: "9.2", unit: "%", flag: "high" }],
    retrieved_docs: [],
    safety_flags: ["hitl_locked"],
    citations: [],
    analysis: {},
    events: [],
    chat_history: [],
    human_decision: { decision: "pending" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderDrawer(run: RunRecord) {
  return render(<HitlDrawer run={run} onReviewed={() => {}} />);
}

describe("HitlDrawer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Approve / Save edits / Reject enabled when awaiting_review", () => {
    renderDrawer(makeRun());
    expect(screen.getByTestId("hitl-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("approve-btn")).toBeEnabled();
    expect(screen.getByTestId("edit-btn")).toBeEnabled();
    expect(screen.getByTestId("reject-btn")).toBeEnabled();
  });

  it("Approve posts decision approve and disables buttons while in flight", async () => {
    const user = userEvent.setup();
    let resolveReview: (value: { run_id: string; status: string }) => void = () => {};
    vi.mocked(submitReview).mockImplementation(
      () => new Promise((resolve) => (resolveReview = resolve)),
    );
    renderDrawer(makeRun());
    await user.click(screen.getByTestId("approve-btn"));
    expect(screen.getByTestId("approve-btn")).toBeDisabled();
    resolveReview({ run_id: "run-test-1", status: "finalized" });
    await waitFor(() => expect(screen.getByTestId("approve-btn")).toBeEnabled());
    expect(submitReview).toHaveBeenCalledWith("run-test-1", { decision: "approve" });
  });

  it("Save edits opens textarea and posts decision edit with the edited text", async () => {
    const user = userEvent.setup();
    renderDrawer(makeRun());
    await user.click(screen.getByTestId("edit-btn"));
    await user.type(screen.getByTestId("hitl-edits"), "Edited recommendation");
    await user.click(screen.getByTestId("edit-save-btn"));
    await waitFor(() =>
      expect(submitReview).toHaveBeenCalledWith("run-test-1", { decision: "edit", edits: "Edited recommendation" }),
    );
  });

  it("Reject opens feedback textarea and posts decision reject with feedback", async () => {
    const user = userEvent.setup();
    renderDrawer(makeRun());
    await user.click(screen.getByTestId("reject-btn"));
    await user.type(screen.getByTestId("hitl-feedback"), "Needs revision");
    await user.click(screen.getByTestId("reject-confirm-btn"));
    await waitFor(() =>
      expect(submitReview).toHaveBeenCalledWith("run-test-1", { decision: "reject", feedback: "Needs revision" }),
    );
  });
});

describe("Disclaimer", () => {
  it("banner contains 'Not for clinical use'", () => {
    render(<Disclaimer />);
    const banner = screen.getByTestId("disclaimer-banner");
    expect(banner).toHaveTextContent("Not for clinical use");
  });
});

describe("Workspace run gating", () => {
  function renderWorkspace() {
    return render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <Workspace />
      </MemoryRouter>,
    );
  }

  it("Run assistant is disabled with empty input", () => {
    renderWorkspace();
    expect(screen.getByTestId("run-assistant-btn")).toBeDisabled();
  });

  it("Run assistant enables once pasted text is provided", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await user.type(screen.getByLabelText("Pasted note text"), "synthetic note text");
    await waitFor(() => expect(screen.getByTestId("run-assistant-btn")).toBeEnabled());
  });
});
