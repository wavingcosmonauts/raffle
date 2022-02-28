# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

"""Python script to run our raffle."""

import contextlib
import random
import subprocess
import tempfile
import time

# TODO know which guild the winning cosmonaut is from
# => convert $STARS to the corresponding reward and receiving address to osmo*

# Our stargaze community pool address  # TODO update
ADDRESS = "stars1msylh4vxq8uyz6cwcerme3yyq3cjpanphs2763"
COSMONAUTS = list(range(384))  # This should be NFT contracts
TEAM_FRAC = 0.2
RAFFLE_FRAC = 1 - TEAM_FRAC


def get_stars_rewards(address):
    """Current number of staking rewards of this Stargaze address."""
    # TODO implement
    rewards = 252
    return rewards * RAFFLE_FRAC, rewards * TEAM_FRAC


def get_holder(nft_id):
    """Retrieve Stargaze address for this NFT."""
    # TODO implement
    return ADDRESS


def get_boost(holder):
    """Probability weight boost for each cosmonaut holder."""
    n_startys = get_num_startys(holder)
    starty_boost = 1.0 + min(n_startys / 10, 1.0)
    return starty_boost


def get_num_startys(holder):
    """Retrieve number of startys this address holds."""
    # TODO implement
    return 0


def get_guild(cosmonaut_id: int):
    """Retrieve guild of this cosmonaut."""
    # TODO implement
    # Simple reading from a traits summary file
    return random.choice(("stars", "osmo", "akt", "luna", "scrt"))


@contextlib.contextmanager
def print_progress(*args, **kwargs):
    print("\t", *args, "...", **kwargs)
    start = time.time()
    yield
    end = time.time()
    print("\t", "...", f"done ({end - start:.2f} s)\n")


def convert_addr(src: str, target: str = "osmo"):
    """Convert src address to target type.

    Typically used to get the corresponding osmo address form the stars one.
    Uses https://github.com/jhernandezb/bech32-convert/releases/tag/v0.0.1
    """
    with tempfile.NamedTemporaryFile(prefix="cosmonaut-raffle", suffix=".txt") as tpath:
        with open(tpath.name, "w") as f:
            f.write(f"{src}\n")
        output = subprocess.run(
            ("./bech32-convert-linux", tpath.name, target),
            capture_output=True,
            check=True,
        )
    addrs = output.stdout.decode().strip().split(",")
    return addrs[1]


def main():
    print("Starting raffle!")
    stars_raffle, stars_team = get_stars_rewards(ADDRESS)
    print(f"Today's 🎁 : {stars_raffle:.2f} $STARS\n")

    with print_progress("Getting all holders"):
        holders = [get_holder(cosmonaut_id) for cosmonaut_id in COSMONAUTS]

    with print_progress("Getting the boost of each holder"):
        boosts = [get_boost(holder) for holder in holders]

    with print_progress("Picking a winner"):
        time.sleep(1)
        (winner_addr,) = random.choices(holders, boosts)
        winner_id = holders.index(winner_addr)
        winner_guild = get_guild(winner_id)
        print(
            f"\n\t\tCongratulations cosmonaut #{winner_id:03d}",
            f"of the {winner_guild} guild 🥂",
        )
        print(
            "\t\tYour quest was successful!",
            f"You found {stars_raffle:.2f} $STARS worth of resources",
        )
        print(f"\n\t\tWinning address: {winner_addr}")
        if winner_guild != "stars":
            osmo_addr = convert_addr(winner_addr)
            print(f"\t\t   Osmo address:  {osmo_addr}")
        print("\n")


if __name__ == "__main__":
    main()
