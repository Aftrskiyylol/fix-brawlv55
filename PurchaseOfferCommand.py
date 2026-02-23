from Heart.Commands.LogicCommand import LogicCommand
from Heart.Messaging import Messaging
import json
import traceback


class PurchaseOfferCommand(LogicCommand):

    def __init__(self, commandData):
        super().__init__(commandData)

    # --------------------------------------------------
    # ENCODE
    # --------------------------------------------------
    def encode(self, fields):
        LogicCommand.encode(self, fields)
        self.writeVInt(1)
        self.writeDataReference(0)
        self.writeVInt(0)
        return self.messagePayload

    # --------------------------------------------------
    # DECODE (FIXED ORDER)
    # --------------------------------------------------
    def decode(self, calling_instance):
        fields = {}
        try:
            LogicCommand.decode(calling_instance, fields, False)

            # ⚠ правильный порядок (Heart 2020-2022 протокол)
            fields["OfferIndex"] = calling_instance.readVInt()
            fields["CurrencyType"] = calling_instance.readVInt()
            fields["ShopCategory"] = calling_instance.readDataReference()
            fields["ItemID"] = calling_instance.readDataReference()
            fields["Price"] = calling_instance.readVInt()
            fields["Unk6"] = calling_instance.readVInt()

            LogicCommand.parseFields(fields)

            print("[PURCHASE DECODE]", fields)

        except Exception as e:
            print("[DECODE ERROR]", e)
            traceback.print_exc()

        return fields

    # --------------------------------------------------
    # EXECUTE
    # --------------------------------------------------
    def execute(self, calling_instance, fields):
        try:
            player = calling_instance.player
            if not player:
                return self.safe_send_home(calling_instance)

            pdata = self.player_to_dict(player)

            offer_index = fields["OfferIndex"]
            currency = fields["CurrencyType"]
            shop_category = fields["ShopCategory"]
            item = fields["ItemID"]
            price = fields["Price"]

            item_category = shop_category[0]
            brawler_id = item[0]
            skin_id = item[1]

            print(f"[PURCHASE] cat={item_category} item={item} price={price} curr={currency}")

            if price <= 0:
                return self.safe_send_home(calling_instance)

            # -------- валюта --------
            if currency == 0:
                if pdata["Gems"] < price:
                    return self.safe_send_home(calling_instance)
                player.Gems -= price

            elif currency == 1:
                if pdata["Coins"] < price:
                    return self.safe_send_home(calling_instance)
                player.Coins -= price

            elif currency == 2:
                if pdata["StarPoints"] < price:
                    return self.safe_send_home(calling_instance)
                player.StarPoints -= price

            # -------- скин --------
            if item_category == 16 and brawler_id and skin_id:
                owned = self.safe_get_owned_brawlers(player)

                key = str(brawler_id)
                if key in owned:
                    if "Skins" not in owned[key]:
                        owned[key]["Skins"] = []

                    if skin_id not in owned[key]["Skins"]:
                        owned[key]["Skins"].append(skin_id)
                        self.safe_set_owned_brawlers(player, owned)
                        print("[PURCHASE] Skin added")

            self.safe_save_player(calling_instance, player)

        except Exception as e:
            print("[EXECUTE ERROR]", e)
            traceback.print_exc()

        self.safe_send_home(calling_instance)

    # --------------------------------------------------
    # SAFE HOME (FIX CONNECTION LEN BUG)
    # --------------------------------------------------
    def safe_send_home(self, calling_instance):
        try:
            from Heart.Packets.Server.OwnHomeDataMessage import OwnHomeDataMessage

            msg = OwnHomeDataMessage(calling_instance)
            buffer = msg.encode()  # ⚠ encode возвращает bytes

            if buffer:
                Messaging.send(calling_instance, buffer)
                print("[HOME] sent")

        except Exception as e:
            print("[HOME ERROR]", e)

    # --------------------------------------------------
    # UTILS
    # --------------------------------------------------
    def player_to_dict(self, player):
        if isinstance(player, dict):
            return player
        if hasattr(player, "__dict__"):
            return player.__dict__
        return {}

    def safe_get_owned_brawlers(self, player):
        if hasattr(player, "OwnedBrawlers"):
            return player.OwnedBrawlers
        return {}

    def safe_set_owned_brawlers(self, player, b):
        player.OwnedBrawlers = b

    def safe_save_player(self, calling_instance, player):
        try:
            if hasattr(calling_instance, "db"):
                data = json.dumps(player.__dict__)
                cur = calling_instance.db.cursor()
                cur.execute(
                    "UPDATE main SET Data=? WHERE Token=?",
                    (data, calling_instance.player_token),
                )
                calling_instance.db.commit()
                print("[DB] saved")
        except Exception as e:
            print("[DB ERROR]", e)

    def getCommandType(self):
        return 519
