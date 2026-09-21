"""
==============================================================
Module: Burnout

Chuc nang:
- Burnout assessment and analysis
- Burnout score calculation
- Routes: /api/burnout/analyze, /latest, /history

Cau truc:
- models/        - BurnoutFactor, BurnoutResult, BurnoutEngineInput, BurnoutEngineOutput
- services/      - BurnoutEngine (algo), BurnoutService (orchestrator)
- repositories/  - BurnoutRepository (Firestore)
- routes/        - FastAPI endpoints
==============================================================
"""

from app.modules.burnout.routes import burnout_result_router

__all__ = ["burnout_result_router"]
