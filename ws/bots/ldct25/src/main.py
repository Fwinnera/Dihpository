"""Entry point for the CAMBC WASI runner; do not run this with desktop Python."""
import cambc as bc


def main():
    print("BOTTAG ldct25", flush=True)


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
