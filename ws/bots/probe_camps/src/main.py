"""Entry point for the CAMBC WASI runner; do not run this with desktop Python."""
import cambc as bc



def _camps():
    import cambc as bc
    from cambc import game_map as gm
    rows = []
    for g in gm.camp_groups():
        cs = g.camps()
        rows.append("%d:%d:%d:%d:%d:%d" % (g.__index__(), g.gem_value(), g.gold_value(),
                    sum(c.base_stats().base_health for c in cs), int(any(c.is_monolith() for c in cs)),
                    sum(c.base_stats().base_strength for c in cs)))
    print("CAMPS altars=%d %s" % (gm.altars().count(), " ".join(rows)), flush=True)

def main():
    print("BOTTAG probe_camps", flush=True)
    if not bc.is_draft():
        pass


    bot = None
    while True:
        try:
            if bc.is_draft():
                import draft
                draft.play()
            else:
                if bot is None:
                    _camps()
                    import policy
                    bot = policy.create_bot()
                import turn
                turn.begin()
                bot.play_turn()
                import navigation
                navigation.finish_turn()
        except Exception as error:
            # Fuel exhaustion resumes inside the old call stack. Rebuild the
            # observation instead of executing yesterday's movement/attack plan.
            if type(error).__name__ == "Replan":
                if bc.round_number() != turn.started:
                    continue
                bc.end_turn()
                continue
            # An uncaught Python exception resigns the whole team. Log and yield.
            # Treat every ERROR in replays as a bug; never silently hide failures.
            frame = error.__traceback__
            location = []
            while frame is not None:
                location.append(f"{frame.tb_frame.f_code.co_filename}:{frame.tb_lineno}")
                frame = frame.tb_next
            print(f"ERROR {type(error).__name__}: {error} @ {' > '.join(location)}", flush=True)
        bc.end_turn()


if __name__ == "__main__":
    main()
