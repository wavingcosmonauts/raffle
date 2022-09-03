# vim: ft=python fileencoding=utf-8 sw=4 et sts=4

"""Python script to run our raffle."""

import asyncio
import base64
import collections
import contextlib
import json
import random
import subprocess
import tempfile
import time

import aiohttp

ADDRESS = "stars1u2cup60zf0dujuhd4sth09gvdc383p0jguaqp3"
TEAM_FRAC = 0.2
COMPOUND_FRAC = 0.2
RAFFLE_FRAC = 1 - TEAM_FRAC - COMPOUND_FRAC

COSMONAUT_MINTER = "stars18tj7yvh7qxv29wtr4angy4gqycrrj9e5j9susaes7vd4tqafzthq5h2m8r"
STARTY_MINTER = "stars1fqsqgjlurc7z2sntulfa0f9alk2ke5npyxrze9deq7lujas7m3ss7vq2fe"
HONOR_STARTY_MINTER = "stars19dzracz083k9plv0gluvnu456frxcrxflaf37ugnj06tdr5xhu5sy3k988"
HU_MINTER = "stars1lnrdwhf4xcx6w6tdpsghgv6uavem353gtgz77sdreyhts883wdjq52aewm"
SK_MINTER = "stars1e3v7h9y3gajtzly37n0g88l9shjlsq2p0pywffty6x676eh6967sg643d2"


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
                base64.encodebytes(
                    f'{{"owner_of":{{"token_id":"{token_id}"}}}}'.encode()
                )
                .decode()
                .strip()
            )
            query_url = f"{api_url}/{sg721}/smart/{query}"
            data = await gather_json(session, query_url)
            try:
                return data["data"]["owner"]
            except KeyError:  # Token not minted yet
                return ""  # Pool wins

        tasks = [get_holder(token_id + 1) for token_id in range(n_tokens)]
        addresses = await asyncio.gather(*tasks)
        return {
            token_id: addr for token_id, addr in enumerate(addresses, start=1) if addr
        }


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


def get_boost(
    holder,
    *,
    cosmonaut_counter,
    starty_counter,
    honor_starty_counter,
    hu_counter,
    sk_counter,
):
    """Probability weight boost for each cosmonaut holder."""
    n_startys = starty_counter.get(holder, 0)
    n_honor_startys = honor_starty_counter.get(holder, 0)
    n_planets = hu_counter.get(holder, 0)
    n_baddies = sk_counter.get(holder, 0)
    n_cosmonauts = cosmonaut_counter[holder]
    # Distribute other NFTs equally over all cosmonauts the holder has
    # This may currently give a fraction of an NFT to each cosmonaut, which is not an
    # issue mathematically, but does not make sense from an explorer point of view
    # TODO consider only fixed integer distribution
    starty_boost = min(n_startys / 10 / n_cosmonauts, 1.0)
    honor_starty_boost = min(n_honor_startys / 10 / n_cosmonauts, 1.0)
    planet_boost = min(n_planets / 30 / n_cosmonauts, 1.0)
    sk_boost = min(n_baddies / 10 / n_cosmonauts, 1.0)
    return 1.0 + starty_boost + honor_starty_boost + planet_boost + sk_boost


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
    path: str = "data/winner_variables.json",
):
    data = {
        "Number": winner_id,
        "Address": winner_addr,
        "Prize": prize,
        "Guild": guild
    }

    with open(path, "w") as f:
        json.dump(data, f)


async def main():
    print("Starting raffle!")
    stars_remainder = 808.50  # Extra $STARS from delayed rewards claiming
    pool_value, pool_rewards = await get_pool_info(ADDRESS)
    pool_rewards += stars_remainder
    stars_raffle = pool_rewards * RAFFLE_FRAC
    stars_team = pool_rewards * TEAM_FRAC
    stars_compound = pool_rewards * COMPOUND_FRAC

    n_winners = 2
    prize = stars_raffle / n_winners

    print(f"      Note : {stars_compound:.2f} $STARS to compound")
    print(f"             {stars_team:.2f} $STARS for the team\n")
    print(f"Today's 🎁 : {prize:.2f} $STARS for {n_winners} cosmonauts\n")

    async with aiohttp.ClientSession() as session:
        url = "https://www.wavingcosmonauts.space/assets/cosmonauts/cosmonaut_data.json"
        cosmonaut_data = await gather_json(session, url)
    guilds = [cosmonaut["Guild"] for cosmonaut in cosmonaut_data]

    with print_progress("Getting all cosmonaut holders"):
        cosmonauts = await get_holders(COSMONAUT_MINTER, 384)
    cosmonaut_counter = collections.Counter(cosmonauts.values())

    with print_progress("Getting all starty holders"):
        startys = await get_holders(STARTY_MINTER, 1111)
    starty_counter = collections.Counter(startys.values())

    with print_progress("Getting all honor starty holders"):
        honor_startys = await get_holders(HONOR_STARTY_MINTER, 1111)
    honor_starty_counter = collections.Counter(honor_startys.values())

    with print_progress("Getting all HU planet holders"):
        hu_planets = await get_holders(HU_MINTER, 5000)
    hu_counter = collections.Counter(hu_planets.values())

    with print_progress("Getting all SK holders"):
        sk_baddies = await get_holders(SK_MINTER, 2000)
    sk_counter = collections.Counter(sk_baddies.values())

    boosts = [
        get_boost(
            holder,
            cosmonaut_counter=cosmonaut_counter,
            starty_counter=starty_counter,
            honor_starty_counter=honor_starty_counter,
            hu_counter=hu_counter,
            sk_counter=sk_counter,
        )
        for holder in cosmonauts.values()
    ]

    with print_progress(f"Picking {n_winners} winners"):
        winner_ids = random.choices(list(cosmonauts), boosts, k=2)

        winners = []

        for winner_id in winner_ids:
            winner_addr = cosmonauts[winner_id]
            winner_guild = guilds[winner_id - 1]
            print(
                f"\n\t\tCongratulations cosmonaut #{winner_id:03d} ",
                f"of the {winner_guild} guild 🥂",
            )
            print(
                "\t\tYour quest was successful!",
                f"You found {prize:.2f} $STARS worth of resources",
            )
            print(f"\n\t\tWinning address: {winner_addr}")
            print("\n")

            winners.append({
                "Number": winner_id,
                "Address": winner_addr,
                "Prize": prize,
                "Guild": winner_guild,
            })

    # Write to file
    with open("data/winner_variables.json", "w") as f:
        json.dump(winners, f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
