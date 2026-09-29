from itertools import product


def simulate(N, G, verbose=True, max_days=None):
    """
    Simulate the Green-Eyed Islanders puzzle.

    N = total population
    G = number of green-eyed islanders
    verbose = print step-by-step reasoning
    max_days = cutoff for simulation (default = N+2)
    """
    all_worlds = list(product([False, True], repeat=N))
    real_world = tuple(
        [i < G for i in range(N)]
    )  # first G are green (arbitrary choice)

    if max_days is None:
        max_days = N + 2  # safe upper bound

    if verbose:
        print(f"Population N={N}, true number of green-eyed G={G}")
        print("Real world (index: green?):")
        print(", ".join(f"{i}:{'G' if real_world[i] else '-'}" for i in range(N)))
        print()

    # After the guru’s announcement: "I see someone with green eyes"
    # All worlds without any green-eyed are eliminated.
    current_common_worlds = [w for w in all_worlds if any(w)]
    if verbose:
        print(f"Initial possible worlds: {len(current_common_worlds)} remain")
        print()

    left = [False] * N
    day = 0
    history = []

    while day < max_days:
        day += 1

        def predicted_leavers_if_world_is(w, common_worlds):
            leavers = set()
            for i in range(N):
                if left[i]:
                    continue
                # Agent i sees others’ eyes
                consistent_worlds = [
                    u
                    for u in common_worlds
                    if all(u[j] == w[j] for j in range(N) if j != i)
                ]
                if not consistent_worlds:
                    continue
                # If in all consistent worlds i is green, they deduce they are green
                if all(u[i] for u in consistent_worlds):
                    leavers.add(i)
            return frozenset(sorted(leavers))

        # Compute actual leavers for the real world
        observed_leavers = predicted_leavers_if_world_is(
            real_world, current_common_worlds
        )

        if verbose:
            print(f"Day {day}: observed leavers -> {sorted(observed_leavers)}")

        for i in observed_leavers:
            left[i] = True
        if observed_leavers:
            history.append((day, sorted(observed_leavers)))

        # Update possible worlds based on the public observation
        new_common_worlds = [
            w
            for w in current_common_worlds
            if predicted_leavers_if_world_is(w, current_common_worlds)
            == observed_leavers
        ]
        if verbose:
            print(
                f"Worlds before update: {len(current_common_worlds)}, after update: {len(new_common_worlds)}"  # noqa: E501
            )
            print()

        if not observed_leavers and len(new_common_worlds) == len(
            current_common_worlds
        ):
            if verbose:
                print("No change in public knowledge and nobody left today. Stopping.")
            break

        current_common_worlds = new_common_worlds

        if all((not real_world[i]) or left[i] for i in range(N)):
            if verbose:
                print("All actual green-eyed have left. Simulation ends.")
            break

    if verbose:
        if history:
            print("Summary of departures:")
            for d, leavers in history:
                print(f"  Day {d}: agents {leavers} left")
            print(
                f"Total green-eyed who left: {sum(1 for i in range(N) if real_world[i] and left[i])} (expected {G})"  # noqa: E501
            )
            print(f"--> last departure day: {history[-1][0]}")
        else:
            print("No departures occurred.")

    return history, real_world, current_common_worlds


# Example runs
if __name__ == "__main__":
    examples = [(5, 1), (5, 2), (5, 3)]
    for N, G in examples:
        print("=" * 60)
        simulate(N, G)
