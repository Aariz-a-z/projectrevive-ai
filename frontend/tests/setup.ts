import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Without this, components from one test stay in the document and the next
// test's queries match the wrong element.
afterEach(() => {
  cleanup();
});
