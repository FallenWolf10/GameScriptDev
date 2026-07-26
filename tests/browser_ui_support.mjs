const DEFAULT_READY_SELECTOR = "#workspace-navigation";
const DEFAULT_RUNTIME_SELECTOR = "#settings-server";
const DEFAULT_MODAL_SELECTOR = "#builder-diff-dialog";
const DEFAULT_CONFIRM_SELECTOR = "#confirm-builder-diff";
const DEFAULT_ERROR_SELECTOR =
  "#app-notice.error:not([hidden]) #app-notice-message";

export class BrowserUiTimeoutError extends Error {}
export class UnexpectedDraftSafetyConfirmationError extends Error {}

function deadlineWaiter(tab, { timeoutMs, intervalMs, now, pause }) {
  const deadline = now() + timeoutMs;
  return {
    expired: () => now() >= deadline,
    pause: () => pause?.(intervalMs) ?? tab.playwright.waitForTimeout(intervalMs),
  };
}

async function visible(locator) {
  return (await locator.count()) === 1 && locator.isVisible();
}

export async function openDashboardForUiTest(
  tab,
  url,
  {
    timeoutMs = 10_000,
    intervalMs = 50,
    readySelector = DEFAULT_READY_SELECTOR,
    runtimeSelector = DEFAULT_RUNTIME_SELECTOR,
    now = Date.now,
    pause,
  } = {},
) {
  await tab.goto(url);
  await tab.playwright.waitForLoadState({
    state: "domcontentloaded",
    timeoutMs,
  });

  const ready = tab.playwright.locator(readySelector);
  const runtime = tab.playwright.locator(runtimeSelector);
  const waiter = deadlineWaiter(tab, { timeoutMs, intervalMs, now, pause });
  while (!waiter.expired()) {
    const runtimeText = (await runtime.textContent())?.trim() || "";
    if (
      (await visible(ready))
      && runtimeText
      && !runtimeText.startsWith("Checking")
    ) {
      return;
    }
    await waiter.pause();
  }
  throw new BrowserUiTimeoutError(
    `Dashboard did not expose its UI-ready sentinel within ${timeoutMs}ms.`,
  );
}

export async function runDestructiveUiAction(
  tab,
  {
    action,
    expectedChange,
    confirmMutation = false,
    timeoutMs = 2_000,
    intervalMs = 50,
    modalSelector = DEFAULT_MODAL_SELECTOR,
    confirmSelector = DEFAULT_CONFIRM_SELECTOR,
    errorSelector = DEFAULT_ERROR_SELECTOR,
    now = Date.now,
    pause,
  },
) {
  const modal = tab.playwright.locator(modalSelector);
  const confirm = tab.playwright.locator(confirmSelector);
  const errorNotice = tab.playwright.locator(errorSelector);
  let actionError = null;
  void Promise.resolve()
    .then(action)
    .catch((error) => {
      actionError = error;
    });

  const waiter = deadlineWaiter(tab, { timeoutMs, intervalMs, now, pause });
  while (!waiter.expired()) {
    if (actionError) throw actionError;
    if (await expectedChange()) {
      return { outcome: "changed", confirmed: false };
    }
    if (await visible(errorNotice)) {
      throw new Error(
        (await errorNotice.textContent())?.trim() || "UI action failed.",
      );
    }
    if (await visible(modal)) {
      if (!confirmMutation) {
        throw new UnexpectedDraftSafetyConfirmationError(
          "Draft Safety confirmation appeared, but this test did not authorize the mutation.",
        );
      }
      if ((await confirm.count()) !== 1) {
        throw new Error("Draft Safety confirmation control is not unique.");
      }
      await confirm.click();
      while (!waiter.expired()) {
        if (actionError) throw actionError;
        if (await expectedChange()) {
          return { outcome: "changed", confirmed: true };
        }
        if (await visible(errorNotice)) {
          throw new Error(
            (await errorNotice.textContent())?.trim() || "UI action failed.",
          );
        }
        await waiter.pause();
      }
      break;
    }
    await waiter.pause();
  }
  throw new BrowserUiTimeoutError(
    `Destructive UI action produced no change, Draft Safety confirmation, or error within ${timeoutMs}ms.`,
  );
}
