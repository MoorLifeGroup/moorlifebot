import os
import csv
import datetime as dt
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp


# ----------------- CONFIG VIA ENV -----------------
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_AUTH_SECRET = os.getenv("WEBHOOK_AUTH_SECRET", "").strip()

GUILD_ID = os.getenv("GUILD_ID", "").strip()           # speeds up slash-command sync if set
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))  # 0 = disabled
QUESTION_TIMEOUT = int(os.getenv("QUESTION_TIMEOUT", "180"))

# Optional CSV fallback if you want local logging too (only meaningful on persistent disk)
CSV_FALLBACK_PATH = os.getenv("CSV_FALLBACK_PATH", "").strip()  # leave empty to disable


# ----------------- DATA MODEL -----------------
@dataclass
class DailyTotals:
    # Required identity / timing
    timestamp_utc: str
    discord_user_id: str
    discord_display_name: str
    start_time: str
    end_time: str

    # Day totals (whole day)
    knocks_total: int
    knocks_category: str                 # "CodeNOx" | "LeadSource" | "ColdKnock" | "Mixed"
    knocks_source_detail: str           # when LeadSource (e.g., Gamechanger/Silver/etc.)
    presentations_no_sale: int
    not_interested: int
    sales_count: int
    ap_amount: float
    carrier: str
    dials_made: int
    appts_booked_total: int
    appts_booked_from_dials: int

    # Cold Knock breakdown (optional; 0/blank if none)
    cold_knocks_total: int = 0
    cold_presentations_no_sale: int = 0
    cold_not_interested: int = 0
    cold_sales_count: int = 0
    cold_ap_amount: float = 0.0
    cold_appts_booked: int = 0

    # Lead-source breakdown (optional)
    lead_knocks_total: int = 0
    lead_presentations_no_sale: int = 0
    lead_not_interested: int = 0
    lead_sales_count: int = 0
    lead_ap_amount: float = 0.0
    lead_appts_booked: int = 0

    # Reliability / Security
    idempotency_key: str = ""
    auth_secret: str = ""


# ----------------- COG -----------------
class ActivityCog(commands.Cog):
    """Conversational daily activity logging with webhook to Zapier."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- Public entrypoints ----------
    @commands.command(name="logday")
    async def logday_prefix(self, ctx: commands.Context):
        """Prefix command: !logday (mirrors the slash command)"""
        await self._start_flow(ctx.author, reply_channel=ctx.channel)

    @app_commands.command(name="logday", description="Log today’s activity in a quick conversational DM flow.")
    async def logday_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Check your DMs — I’ll walk you through the daily log.",
            ephemeral=True
        )
        await self._start_flow(interaction.user, reply_channel=None)

    # Register slash command to a single guild (fast) if GUILD_ID is set
    @logday_slash.error
    async def _slash_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.followup.send(f"Error: {error}", ephemeral=True)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        # Try to sync the slash command if GUILD_ID is present
        try:
            if GUILD_ID:
                guild = discord.Object(id=int(GUILD_ID))
                self.bot.tree.copy_global_to(guild=guild)
                await self.bot.tree.sync(guild=guild)
                print(f"[activities] Slash commands synced to guild {GUILD_ID}")
            else:
                # Try a global sync silently; may take longer to propagate first time
                await self.bot.tree.sync()
                print("[activities] Slash commands synced globally")
        except Exception as e:
            print("[activities] Slash command sync failed:", e)

    # ---------- Flow logic ----------
    async def _start_flow(self, user: discord.User | discord.Member, reply_channel: Optional[discord.abc.Messageable] = None):
        # Open DM
        try:
            dm = await user.create_dm()
        except discord.Forbidden:
            if reply_channel:
                await reply_channel.send("I can’t DM you. Enable DMs from server members and try again.")
            return

        await dm.send(
            "**Daily Log — Moor Life Group / Summit Strength**\n"
            "Answer a few quick questions. Type `cancel` anytime to stop.\n"
        )

        # Identity + timing
        start_time = await self._ask_text(dm, user, "Start time (e.g., `9:00 AM`): ")
        if start_time is None: return
        end_time = await self._ask_text(dm, user, "End time (e.g., `5:30 PM`): ")
        if end_time is None: return

        # Totals first (whole day picture)
        knocks_total = await self._ask_int(dm, user, "Total NOx (all knocks today): ")
        if knocks_total is None: return

        knocks_category = await self._ask_choice(
            dm, user,
            "Primary knocks category? Reply with `CodeNOx`, `LeadSource`, or `ColdKnock`. If you did both cold and lead today, reply `Mixed`.",
            choices=["CODENOX", "LEADSOURCE", "COLDKNOCK", "MIXED"]
        )
        if knocks_category is None: return

        knocks_source_detail = ""
        if knocks_category in ("LEADSOURCE", "MIXED"):
            knocks_source_detail = await self._ask_text(dm, user, "Lead source/batch? (e.g., `Gamechanger`, `Silver`, `Integrity Preferred`): ")
            if knocks_source_detail is None: return
        else:
            knocks_source_detail = ""

        presentations_no_sale = await self._ask_int(dm, user, "Presentations with **no sale** (total today): ")
        if presentations_no_sale is None: return

        not_interested = await self._ask_int(dm, user, "`Not interested` count (total today): ")
        if not_interested is None: return

        sales_count = await self._ask_int(dm, user, "Sales closed (count, total today): ")
        if sales_count is None: return

        ap_amount = await self._ask_float(dm, user, "Total AP (e.g., `1243.50`): ")
        if ap_amount is None: return

        carrier = await self._ask_text(dm, user, "Carrier (e.g., `Aetna`, `Americo`, `MOO`, `Nassau`): ")
        if carrier is None: return

        dials_made = await self._ask_int(dm, user, "Dials made (total today): ")
        if dials_made is None: return

        appts_booked_total = await self._ask_int(dm, user, "Appointments booked (total today): ")
        if appts_booked_total is None: return

        appts_booked_from_dials = await self._ask_int(dm, user, "Appointments booked **from dials** (subset of total): ")
        if appts_booked_from_dials is None: return

        # Optional: Cold Knock breakdown
        cold_knocks_total = cold_presentations_no_sale = cold_not_interested = cold_sales_count = cold_appts_booked = 0
        cold_ap_amount = 0.0
        had_cold = await self._ask_yes_no(dm, user, "Did you do **Cold Knocks** today? (`yes`/`no`): ")
        if had_cold is None: return
        if had_cold:
            cold_knocks_total = await self._ask_int(dm, user, "Cold Knocks — total knocks: ")
            if cold_knocks_total is None: return
            cold_presentations_no_sale = await self._ask_int(dm, user, "Cold Knocks — presentations with no sale: ")
            if cold_presentations_no_sale is None: return
            cold_not_interested = await self._ask_int(dm, user, "Cold Knocks — not interested count: ")
            if cold_not_interested is None: return
            cold_sales_count = await self._ask_int(dm, user, "Cold Knocks — sales count: ")
            if cold_sales_count is None: return
            cold_ap_amount = await self._ask_float(dm, user, "Cold Knocks — AP amount (e.g., `500`): ")
            if cold_ap_amount is None: return
            cold_appts_booked = await self._ask_int(dm, user, "Cold Knocks — appointments booked: ")
            if cold_appts_booked is None: return

        # Optional: Lead-source breakdown
        lead_knocks_total = lead_presentations_no_sale = lead_not_interested = lead_sales_count = lead_appts_booked = 0
        lead_ap_amount = 0.0
        had_leads = await self._ask_yes_no(dm, user, "Did you work **Lead-source knocks** today? (`yes`/`no`): ")
        if had_leads is None: return
        if had_leads:
            lead_knocks_total = await self._ask_int(dm, user, "Lead-source — total knocks: ")
            if lead_knocks_total is None: return
            lead_presentations_no_sale = await self._ask_int(dm, user, "Lead-source — presentations with no sale: ")
            if lead_presentations_no_sale is None: return
            lead_not_interested = await self._ask_int(dm, user, "Lead-source — not interested count: ")
            if lead_not_interested is None: return
            lead_sales_count = await self._ask_int(dm, user, "Lead-source — sales count: ")
            if lead_sales_count is None: return
            lead_ap_amount = await self._ask_float(dm, user, "Lead-source — AP amount (e.g., `750`): ")
            if lead_ap_amount is None: return
            lead_appts_booked = await self._ask_int(dm, user, "Lead-source — appointments booked: ")
            if lead_appts_booked is None: return

        # Build payload
        timestamp_utc = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        display_name = getattr(user, "display_name", None) or user.name

        payload = DailyTotals(
            timestamp_utc=timestamp_utc,
            discord_user_id=str(user.id),
            discord_display_name=display_name,
            start_time=start_time,
            end_time=end_time,
            knocks_total=knocks_total,
            knocks_category=knocks_category,              # already uppercased in _ask_choice
            knocks_source_detail=knocks_source_detail,
            presentations_no_sale=presentations_no_sale,
            not_interested=not_interested,
            sales_count=sales_count,
            ap_amount=float(ap_amount),
            carrier=carrier,
            dials_made=dials_made,
            appts_booked_total=appts_booked_total,
            appts_booked_from_dials=appts_booked_from_dials,
            cold_knocks_total=cold_knocks_total,
            cold_presentations_no_sale=cold_presentations_no_sale,
            cold_not_interested=cold_not_interested,
            cold_sales_count=cold_sales_count,
            cold_ap_amount=float(cold_ap_amount),
            cold_appts_booked=cold_appts_booked,
            lead_knocks_total=lead_knocks_total,
            lead_presentations_no_sale=lead_presentations_no_sale,
            lead_not_interested=lead_not_interested,
            lead_sales_count=lead_sales_count,
            lead_ap_amount=float(lead_ap_amount),
            lead_appts_booked=lead_appts_booked,
            idempotency_key=f"{user.id}-{timestamp_utc}",
            auth_secret=WEBHOOK_AUTH_SECRET or "",
        )

        # Send to Zapier webhook
        ok, err = await self._post_webhook(asdict(payload)) if WEBHOOK_URL else (True, None)

        # Optional CSV fallback (only if a path is provided)
        if CSV_FALLBACK_PATH:
            try:
                self._append_csv(payload)
            except Exception as e:
                # Non-fatal; user already posted
                err = err or f"CSV fallback error: {e}"

        # DM summary
        if ok:
            await dm.send(self._format_summary(payload))
            # Optional: echo into a log channel for accountability
            if LOG_CHANNEL_ID:
                channel = self.bot.get_channel(LOG_CHANNEL_ID)
                if channel:
                    try:
                        await channel.send(self._format_public_summary(payload))
                    except Exception:
                        pass
        else:
            await dm.send(f"❌ I couldn’t post your log to the webhook. Error: `{err}`")

    # ---------- Helpers: ask/validate ----------
    async def _ask_text(self, dm: discord.DMChannel, user: discord.User, prompt: str) -> Optional[str]:
        await dm.send(prompt)
        resp = await self._wait_for(dm, user)
        if not resp: return None
        content = resp.content.strip()
        if content.lower() == "cancel":
            await dm.send("❎ Cancelled.")
            return None
        return content

    async def _ask_int(self, dm: discord.DMChannel, user: discord.User, prompt: str) -> Optional[int]:
        await dm.send(prompt)
        while True:
            resp = await self._wait_for(dm, user)
            if not resp: return None
            content = resp.content.strip().lower()
            if content == "cancel":
                await dm.send("❎ Cancelled.")
                return None
            try:
                val = int(content.replace(",", ""))
                if val < 0: raise ValueError
                return val
            except ValueError:
                await dm.send("Please reply with a non-negative whole number:")

    async def _ask_float(self, dm: discord.DMChannel, user: discord.User, prompt: str) -> Optional[float]:
        await dm.send(prompt)
        while True:
            resp = await self._wait_for(dm, user)
            if not resp: return None
            content = resp.content.strip().lower()
            if content == "cancel":
                await dm.send("❎ Cancelled.")
                return None
            try:
                val = float(content.replace(",", ""))
                if val < 0: raise ValueError
                return val
            except ValueError:
                await dm.send("Please reply with a non-negative number (e.g., `1250` or `1250.50`):")

    async def _ask_choice(self, dm: discord.DMChannel, user: discord.User, prompt: str, choices: list[str]) -> Optional[str]:
        await dm.send(prompt)
        upper = [c.upper() for c in choices]
        while True:
            resp = await self._wait_for(dm, user)
            if not resp: return None
            content = resp.content.strip().upper()
            if content == "CANCEL":
                await dm.send("❎ Cancelled.")
                return None
            if content in upper:
                return content
            pretty = " / ".join(choices)
            await dm.send(f"Please reply with one of: `{pretty}`")

    async def _ask_yes_no(self, dm: discord.DMChannel, user: discord.User, prompt: str) -> Optional[bool]:
        await dm.send(prompt)
        while True:
            resp = await self._wait_for(dm, user)
            if not resp: return None
            content = resp.content.strip().lower()
            if content == "cancel":
                await dm.send("❎ Cancelled.")
                return None
            if content in ("y", "yes"): return True
            if content in ("n", "no"): return False
            await dm.send("Please reply `yes` or `no`:")

    async def _wait_for(self, dm: discord.DMChannel, user: discord.User) -> Optional[discord.Message]:
        def check(m: discord.Message):
            return m.author.id == user.id and m.channel.id == dm.id
        try:
            return await self.bot.wait_for("message", check=check, timeout=QUESTION_TIMEOUT)
        except Exception:
            try:
                await dm.send("⏱️ Timed out. You can start again with `/logday` or `!logday` anytime.")
            except Exception:
                pass
            return None

    # ---------- Helpers: outputs ----------
    def _format_summary(self, p: DailyTotals) -> str:
        return (
            f"**Daily Log Saved**\n"
            f"**User:** {p.discord_display_name} ({p.discord_user_id})\n"
            f"**Window:** {p.start_time} → {p.end_time}\n"
            f"**NOx (total):** {p.knocks_total}  •  **Category:** {p.knocks_category}"
            + (f"  •  **Source:** {p.knocks_source_detail}" if p.knocks_source_detail else "")
            + "\n"
            f"**Pres (no sale):** {p.presentations_no_sale}  •  **Not interested:** {p.not_interested}\n"
            f"**Sales:** {p.sales_count}  •  **AP:** ${p.ap_amount:,.2f}  •  **Carrier:** {p.carrier}\n"
            f"**Dials:** {p.dials_made}  •  **Appts (total/from dials):** {p.appts_booked_total}/{p.appts_booked_from_dials}\n"
            f"**Cold:** K {p.cold_knocks_total} | PresNS {p.cold_presentations_no_sale} | NI {p.cold_not_interested} | Sales {p.cold_sales_count} | AP ${p.cold_ap_amount:,.2f} | Appts {p.cold_appts_booked}\n"
            f"**Lead:** K {p.lead_knocks_total} | PresNS {p.lead_presentations_no_sale} | NI {p.lead_not_interested} | Sales {p.lead_sales_count} | AP ${p.lead_ap_amount:,.2f} | Appts {p.lead_appts_booked}\n"
            f"_UTC: {p.timestamp_utc}_"
        )

    def _format_public_summary(self, p: DailyTotals) -> str:
        return (
            f"📊 **Daily Log — {p.discord_display_name}**\n"
            f"🕘 {p.start_time} → {p.end_time}  •  NOx **{p.knocks_total}**  •  {p.knocks_category}"
            + (f" • {p.knocks_source_detail}" if p.knocks_source_detail else "")
            + "\n"
            f"🎯 Sales **{p.sales_count}**  •  AP **${p.ap_amount:,.2f}**  •  Carrier **{p.carrier}**\n"
            f"📞 Dials **{p.dials_made}**  •  Appts **{p.appts_booked_total}** (from dials **{p.appts_booked_from_dials}**)\n"
            f"🧾 PresNS {p.presentations_no_sale}  •  NI {p.not_interested}\n"
            f"❄️ Cold: K {p.cold_knocks_total} / Sales {p.cold_sales_count} / AP ${p.cold_ap_amount:,.2f} / Appts {p.cold_appts_booked}\n"
            f"📇 Lead: K {p.lead_knocks_total} / Sales {p.lead_sales_count} / AP ${p.lead_ap_amount:,.2f} / Appts {p.lead_appts_booked}\n"
            f"_UTC: {p.timestamp_utc}_"
        )

    # ---------- Helpers: webhook & CSV ----------
    async def _post_webhook(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        try:
            async with aiohttp.ClientSession(raise_for_status=False) as session:
                async with session.post(
                    WEBHOOK_URL,
                    json=data,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                ) as resp:
                    if 200 <= resp.status < 300:
                        return True, None
                    text = await resp.text()
                    return False, f"HTTP {resp.status}: {text[:300]}"
        except Exception as e:
            return False, str(e)

    def _append_csv(self, payload: DailyTotals):
        if not CSV_FALLBACK_PATH:
            return
        write_headers = not os.path.exists(CSV_FALLBACK_PATH)
        with open(CSV_FALLBACK_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if write_headers:
                w.writerow(list(asdict(payload).keys()))
            w.writerow(list(asdict(payload).values()))


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityCog(bot))
