"""One legal pick per invocation, for any map's roster size."""
import cambc as bc
from roster import DRAFT_ORDER
import policy


def play():
    chosen = bc.draft.current_draft(bc.Team.ALLY)
    # The runner resumes this instance for later picks. Gameplay instances are fresh.
    variant = policy.kind()
    if variant == 2:
        D = bc.ChampionDraft
        order = (D.VARG, D.WILLOW, D.RYTH, D.VENDETTA, D.MARCELLA,
                 D.CASSI_AND_ISSAC, D.TAVI, D.STELLAR, D.HEART_OF_RUIN,
                 D.REN, D.PRISM, D.VESPER_VALE)
    else:
        order = DRAFT_ORDER
    bc.draft_memory.submit(b"bomba" + bytes([variant]))
    for pick in order:
        if pick not in chosen:
            bc.draft.pick(pick)
            return
