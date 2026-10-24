"""Entry point for the CAMBC WASI runner; do not run this with desktop Python."""
import cambc as bc


def main():
    print("BOTTAG probe_altar", flush=True)


    bot = None
    while True:
        try:
            if bc.is_draft():
                import draft
                draft.play()
            else:
                if bot is None:
                    from cambc import game_map as _gm
                    import navigation as _n
                    walls, holes, spawnA = _gm.walls(), _gm.holes(), _gm.spawn_region(bc.Team.ALLY)
                    camps = bc.Bitboard()
                    for g in _gm.camp_groups():
                        camps |= g.spawn_tiles()
                    mono = bc.Bitboard()
                    for g in _gm.camp_groups():
                        if any(c.is_monolith() for c in g.camps()):
                            mono |= g.spawn_tiles()
                    for a in _gm.altars().positions():
                        for y in range(a.y - 7, a.y + 8):
                            row = ''
                            for x in range(a.x - 9, a.x + 10):
                                v = bc.Vec2(x, y)
                                try:
                                    row += ('A' if (x, y) == (a.x, a.y) else 'M' if mono.is_set(v) else 'c' if camps.is_set(v) else '#' if walls.is_set(v) else 'o' if holes.is_set(v) else '.')
                                except Exception:
                                    row += ' '
                            print('ALT %3d %s' % (y, row), flush=True)
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
