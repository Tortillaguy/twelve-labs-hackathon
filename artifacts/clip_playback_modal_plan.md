# Implementation Plan: Clip Playback Modal

Implement a global modal overlay for clip playback using React Context and portals, as specified in `docs/superpowers/specs/2026-03-29-clip-playback-modal-design.md`.

## Tasks

### 1. Context: Global Clip State
- **File:** `src/context/ClipPlayerContext.tsx`
- **Action:** 
    - Create `ClipData` interface.
    - Implement `ClipPlayerContext` and `ClipPlayerProvider`.
    - Export `useClipPlayer` hook for easy access.
- **Verification:** Unit test for context or manual check by wrapping a test component.

### 2. Component: Global Modal
- **File:** `src/components/ClipPlayerModal.tsx`
- **Action:** 
    - Implement the modal using `ReactDOM.createPortal`.
    - Use the design from the mockup (black overlay, centered card, 16:9 video).
    - Extract `HlsPlayer` logic from `PlayerDetail.tsx` into a reusable internal component.
    - Add keyboard listeners (`Escape`).
- **Verification:** Visual check in browser, test Escape key.

### 3. App: Integration
- **File:** `src/App.tsx`
- **Action:** 
    - Wrap the app in `ClipPlayerProvider`.
    - Add `ClipPlayerModal` near the top level (sibling to `BrowserRouter`).
- **Verification:** Ensure modal renders in the portal but doesn't block other elements.

### 4. Refactor: Player Detail
- **File:** `src/pages/PlayerDetail.tsx`
- **Action:** 
    - Remove local `activeClip` state.
    - Remove inline `HlsPlayer` component.
    - Hook up `HighlightCard` and `SearchClipCard` to `openClip` from context.
- **Verification:** Manual check of both "Verified Highlights" and "Global AI Discovery" cards to confirm they open the global modal.

## Overall Verification
- Open a clip, navigate to another page, ensure modal stays.
- Close the modal and ensure HLS instance is destroyed.
- Test backdrop click and Escape key.
