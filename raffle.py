# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

"""Python script to run our raffle."""

import asyncio
import base64
import collections
import contextlib
import datetime
import random
import subprocess
import tempfile
import time

import aiohttp

ADDRESS = "stars1u2cup60zf0dujuhd4sth09gvdc383p0jguaqp3"
TEAM_FRAC = 0.384
RAFFLE_FRAC = 1 - TEAM_FRAC

STARTY_MINTER = "stars1fqsqgjlurc7z2sntulfa0f9alk2ke5npyxrze9deq7lujas7m3ss7vq2fe"
COSMONAUT_MINTER = STARTY_MINTER  # TODO update once online


async def get_holders(
    minter_addr: str,
    n_tokens: int,
    api_url: str = "https://rest.stargaze-apis.com/cosmwasm/wasm/v1/contract/",
):
    async with aiohttp.ClientSession() as session:
        sg721_url = f"{api_url}/{minter_addr}/smart/eyJjb25maWciOnt9fQ=="
        data = await gather_json(session, sg721_url)
        sg721 = data["data"]["sg721_address"]

        async def get_holder(token_id: int):
            query = (
                base64.encodebytes(f'{{"owner_of":{{"token_id":"{token_id}"}}}}'.encode())
                .decode()
                .strip()
            )
            query_url = f"{api_url}/{sg721}/smart/{query}"
            data = await gather_json(session, query_url)
            try:
                return data["data"]["owner"]
            except KeyError:  # Token not minted yet
                return ""  # Pool wins

        tasks = [get_holder(i + 1) for i in range(n_tokens)]
        return await asyncio.gather(*tasks)


async def gather_json(session: aiohttp.ClientSession, url: str):
    async with session.get(url) as response:
        return await response.json()


async def get_pool_info(address, api_url="https://rest.stargaze-apis.com/cosmos"):
    """Pool value and current rewards via rest API.

    Useful links:
        https://api.akash.smartnodes.one/swagger/#/
        https://github.com/Smart-Nodes/endpoints
    """
    rewards_url = f"{api_url}/distribution/v1beta1/delegators/{ADDRESS}/rewards"

    delegated_url = f"{api_url}/staking/v1beta1/delegations/{ADDRESS}"

    async with aiohttp.ClientSession() as session:
        rewards_data, pool_data = await asyncio.gather(
            gather_json(session, rewards_url), gather_json(session, delegated_url)
        )
    rewards = float(rewards_data["rewards"][0]["reward"][0]["amount"]) / 1_000_000
    pool_value = (
        float(pool_data["delegation_responses"][0]["balance"]["amount"]) / 1_000_000
    )

    return pool_value, rewards


def get_boost(holder, cosmonaut_counter, starty_counter):
    """Probability weight boost for each cosmonaut holder."""
    n_startys = starty_counter.get(holder, 0)
    n_cosmonauts = cosmonaut_counter[holder]
    # Distribute startys equally over all cosmonauts the holder has
    # This may currently give a fraction of a starty to each cosmonaut, which is not an
    # issue mathematically, but does not make sense from an explorer point of view
    # TODO consider only fixed integer distribution
    starty_boost = 1.0 + min(n_startys / 10 / n_cosmonauts, 1.0)
    return starty_boost


def get_guild(cosmonaut_id: int):
    """Retrieve guild of this cosmonaut."""
    # TODO implement once all cosmonauts are minted
    # Simple reading from a traits summary file
    raise NotImplementedError("Waiting for the mint to complete")


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
    path: str = "data/winner_variables.js",
):
    with open(path, "w") as f:
        f.write(f'const winnerNumber = "{winner_id:03d}";\n')
        f.write(f'const winnerAddress = "{winner_addr}";\n')
        # TODO add back once all are minted
        # f.write(f'const guild = "{guild}";\n')
        # TODO Consider actual token and / or USD value
        # Issue with token: swap fee + time difference to osmosis will make the actual
        # number different
        f.write(f'const prize = "{prize:.2f} $STARS";\n')


async def main():
    print("Starting raffle!")
    pool_value, pool_rewards = await get_pool_info(ADDRESS)
    stars_raffle = pool_rewards * RAFFLE_FRAC
    print(f"Today's 🎁 : {stars_raffle:.2f} $STARS\n")

    with print_progress("Getting all cosmonaut holders"):
        cosmonauts = await get_holders(COSMONAUT_MINTER, 384)
    cosmonaut_counter = collections.Counter(cosmonauts)

    with print_progress("Getting all starty holders"):
        startys = await get_holders(STARTY_MINTER, 1111)
    starty_counter = collections.Counter(startys)

    boosts = [
        get_boost(holder, cosmonaut_counter, starty_counter) for holder in cosmonauts
    ]

    with print_progress("Picking a winner"):
        winner_addr, = random.choices(cosmonauts, boosts)
        winner_id = cosmonauts.index(winner_addr)
        print(
            f"\n\t\tCongratulations cosmonaut #{winner_id:03d} 🥂",
            # TODO add back f"of the {winner_guild} guild 🥂",
        )
        print(
            "\t\tYour quest was successful!",
            f"You found {stars_raffle:.2f} $STARS worth of resources",
        )
        print(f"\n\t\tWinning address: {winner_addr}")
        osmo_addr = convert_addr(winner_addr)
        print(f"\t\t   Osmo address:  {osmo_addr}")
        print("\n")

    update_winner_file(
        winner_id=winner_id,
        winner_addr=winner_addr,
        prize=stars_raffle,
    )


if __name__ == "__main__":
    asyncio.run(main())
