"""One legal pick per invocation, for any map's roster size."""
import cambc as bc
from roster import DRAFT_ORDER


def play():
    chosen = bc.draft.current_draft(bc.Team.ALLY)
    # The runner resumes this instance for later picks. Gameplay instances are fresh.
    bc.draft_memory.submit(b"control-bot-v2")
    for pick in DRAFT_ORDER:
        if pick not in chosen:
            bc.draft.pick(pick)
            return
