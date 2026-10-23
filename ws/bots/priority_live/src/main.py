"""Entry point for the CAMBC WASI runner; do not run this with desktop Python."""
import cambc as bc


def main():
    bot = None
    while True:
        try:
            if bc.is_draft():
                import draft
                draft.play()
            else:
                if bot is None:
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
            # A host getter can suspend for fuel and then report lost vision
            # before control reaches another turn.check(). Re-observe only this
            # typed stale-turn case; current-turn errors still follow the log.
            if (isinstance(error, bc.Error)
                    and error.code == bc.ErrorCode.API_NOT_IN_VISION
                    and 'turn' in locals()
                    and bc.round_number() != turn.started):
                print(f'REPLAN_STALE_VISION started={turn.started} now={bc.round_number()}', flush=True)
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
