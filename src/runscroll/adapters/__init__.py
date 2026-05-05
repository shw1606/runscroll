"""Optional-dependency adapters.

Each adapter module imports its third-party dependency at module import
time. The Collector dispatches to an adapter only when it sees an input
of that adapter's type — and uses module/class name detection (no real
import) to decide, so ``import runscroll`` never pulls Pillow / numpy /
matplotlib / plotly.
"""
