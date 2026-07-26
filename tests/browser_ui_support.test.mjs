import assert from "node:assert/strict";
import test from "node:test";

import {
  BrowserUiTimeoutError,
  UnexpectedDraftSafetyConfirmationError,
  openDashboardForUiTest,
  runDestructiveUiAction,
} from "./browser_ui_support.mjs";

function fakeClock() {
  let value = 0;
  return {
    now: () => value,
    pause: async (milliseconds) => {
      value += milliseconds;
    },
  };
}

function fakeTab(elements = {}) {
  const calls = [];
  const locator = (selector) => {
    const element = elements[selector] || {};
    return {
      count: async () => element.count ?? 1,
      isVisible: async () => Boolean(element.visible),
      textContent: async () => (
        typeof element.text === "function" ? element.text() : element.text
      ) ?? "",
      click: async () => {
        calls.push(["click", selector]);
        await element.click?.();
      },
    };
  };
  return {
    calls,
    goto: async (url) => calls.push(["goto", url]),
    playwright: {
      locator,
      waitForLoadState: async (options) => {
        calls.push(["waitForLoadState", options]);
      },
      waitForTimeout: async () => {
        throw new Error("Tests must inject the fake clock pause.");
      },
    },
  };
}

test("dashboard readiness uses DOM content plus an initialized UI sentinel", async () => {
  const clock = fakeClock();
  let runtimeChecks = 0;
  const tab = fakeTab({
    "#workspace-navigation": { visible: true },
    "#settings-server": {
      text: () => (++runtimeChecks === 1 ? "Checking…" : "127.0.0.1:8893"),
    },
  });

  await openDashboardForUiTest(tab, "http://127.0.0.1:8893/", {
    timeoutMs: 500,
    now: clock.now,
    pause: clock.pause,
  });

  assert.deepEqual(tab.calls.slice(0, 2), [
    ["goto", "http://127.0.0.1:8893/"],
    ["waitForLoadState", { state: "domcontentloaded", timeoutMs: 500 }],
  ]);
  assert.equal(
    tab.calls.some(([, options]) => options?.state === "networkidle"),
    false,
  );
});

test("destructive action confirms Draft Safety only when mutation is intended", async () => {
  const clock = fakeClock();
  let changed = false;
  const modal = { visible: false };
  const tab = fakeTab({
    "#builder-diff-dialog": modal,
    "#confirm-builder-diff": {
      click: async () => {
        modal.visible = false;
        changed = true;
      },
    },
    "#app-notice.error:not([hidden]) #app-notice-message": {
      visible: false,
    },
  });

  const result = await runDestructiveUiAction(tab, {
    action: async () => {
      modal.visible = true;
    },
    expectedChange: async () => changed,
    confirmMutation: true,
    now: clock.now,
    pause: clock.pause,
  });

  assert.deepEqual(result, { outcome: "changed", confirmed: true });
  assert.deepEqual(tab.calls, [["click", "#confirm-builder-diff"]]);
});

test("destructive action fails fast on an unauthorized Draft Safety modal", async () => {
  const clock = fakeClock();
  const tab = fakeTab({
    "#builder-diff-dialog": { visible: true },
    "#confirm-builder-diff": {},
    "#app-notice.error:not([hidden]) #app-notice-message": {
      visible: false,
    },
  });

  await assert.rejects(
    runDestructiveUiAction(tab, {
      action: async () => {},
      expectedChange: async () => false,
      now: clock.now,
      pause: clock.pause,
    }),
    UnexpectedDraftSafetyConfirmationError,
  );
  assert.deepEqual(tab.calls, []);
});

test("destructive action reports a visible UI error instead of polling", async () => {
  const clock = fakeClock();
  const errorNotice = { visible: false, text: "Draft version conflict." };
  const tab = fakeTab({
    "#builder-diff-dialog": { visible: false },
    "#confirm-builder-diff": {},
    "#app-notice.error:not([hidden]) #app-notice-message": errorNotice,
  });

  await assert.rejects(
    runDestructiveUiAction(tab, {
      action: async () => {
        errorNotice.visible = true;
      },
      expectedChange: async () => false,
      now: clock.now,
      pause: clock.pause,
    }),
    /Draft version conflict/,
  );
});

test("destructive action has a deadline rather than a fixed-count loop", async () => {
  const clock = fakeClock();
  const tab = fakeTab({
    "#builder-diff-dialog": { visible: false },
    "#confirm-builder-diff": {},
    "#app-notice.error:not([hidden]) #app-notice-message": {
      visible: false,
    },
  });

  await assert.rejects(
    runDestructiveUiAction(tab, {
      action: async () => {},
      expectedChange: async () => false,
      timeoutMs: 120,
      intervalMs: 50,
      now: clock.now,
      pause: clock.pause,
    }),
    BrowserUiTimeoutError,
  );
});
