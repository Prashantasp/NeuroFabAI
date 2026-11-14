"use client";

import { useState } from "react";

/**
 * Run a reset when a value changes, *during render* rather than in an effect.
 *
 * This is React's documented pattern for "adjusting state when a prop changes"
 * (https://react.dev/learn/you-might-not-need-an-effect). Doing it in an effect
 * causes a visible intermediate render with stale state and trips the
 * `react-hooks/set-state-in-effect` rule; React re-renders the component
 * immediately instead, before committing anything to the DOM.
 *
 * The reset callback must only call setState functions.
 */
export function useResetOnChange<T>(value: T, reset: () => void): void {
  const [previous, setPrevious] = useState(value);

  if (!Object.is(previous, value)) {
    setPrevious(value);
    reset();
  }
}
