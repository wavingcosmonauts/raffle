# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

"""Python script to run our raffle."""

import contextlib
import datetime
import random
import requests
import subprocess
import tempfile
import time

ADDRESS = "stars1u2cup60zf0dujuhd4sth09gvdc383p0jguaqp3"
COSMONAUTS = list(range(384))  # This should be NFT contracts
TEAM_FRAC = 0.384
RAFFLE_FRAC = 1 - TEAM_FRAC


def get_pool_info(address, api_url="https://rest.stargaze-apis.com/cosmos"):
    """Pool value and current rewards via rest API.

    Useful links:
        https://api.akash.smartnodes.one/swagger/#/
        https://github.com/Smart-Nodes/endpoints
    """
    rewards_url = f"{api_url}/distribution/v1beta1/delegators/{ADDRESS}/rewards"
    response_rewards = requests.get(rewards_url)
    data = response_rewards.json()
    rewards = float(data["rewards"][0]["reward"][0]["amount"]) / 1_000_000

    delegated_url = f"{api_url}/staking/v1beta1/delegations/{ADDRESS}"
    response_delegated = requests.get(delegated_url)
    data = response_delegated.json()
    pool_value = (
        float(data["delegation_responses"][0]["delegation"]["shares"]) / 1_000_000
    )

    return pool_value, rewards


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


def update_winner_file(
    *,
    winner_id,
    winner_addr,
    prize,
    guild,
    pool_value,
    path: str = "data/winner_variables.js",
):
    today = datetime.date.today()
    next_raffle = today + datetime.timedelta(days=7)

    with open(path, "w") as f:
        f.write(f'const date = "{today}";\n')
        f.write(f'const nextDate = "{next_raffle}";\n')
        f.write(f'const winnerNumber = "{winner_id:03d}";\n')
        f.write(f'const winnerAddress = "{winner_addr}";\n')
        f.write(f'const guild = "{guild}";\n')
        # TODO
        # Consider actual token and / or USD value
        # Issue with token: swap fee + time difference to osmosis will make the actual
        # number different
        f.write(f'const prize = "{prize:.2f} $STARS";\n')
        f.write(f'const poolValue = "{pool_value:,.0f} $STARS";\n')


def main():
    print("Starting raffle!")
    pool_value, pool_rewards = get_pool_info(ADDRESS)
    stars_raffle = pool_rewards * RAFFLE_FRAC
    print(f"Today's 🎁 : {stars_raffle:.2f} $STARS\n")

    with print_progress("Getting all holders"):
        holders = [get_holder(cosmonaut_id) for cosmonaut_id in COSMONAUTS]

    with print_progress("Getting the boost of each holder"):
        boosts = [get_boost(holder) for holder in holders]

    with print_progress("Picking a winner"):
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

    update_winner_file(
        winner_id=winner_id,
        winner_addr=winner_addr,
        prize=stars_raffle,
        guild=winner_guild,
        pool_value=pool_value,
    )


if __name__ == "__main__":
    main()
