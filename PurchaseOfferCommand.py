from Heart.Commands.LogicCommand import LogicCommand
from Heart.Messaging import Messaging
import traceback


class PurchaseOfferCommand(LogicCommand):

    def __init__(self, commandData):
        super().__init__(commandData)

    # --------------------------------
    # SAFE DECODE (без bytearray error)
    # --------------------------------
    def decode(self, calling_instance):
        fields = {}

        try:
            LogicCommand.decode(self, calling_instance, False)

            # если payload пустой — это shop refresh
            if not hasattr(self, "messagePayload") or not self.messagePayload:
                print("[DECODE] Empty payload (shop refresh)")
                return fields

            # SAFE чтение
            try:
                fields["OfferIndex"] = self.readVInt()
                fields["CurrencyType"] = self.readVInt()
                fields["ShopCategory"] = self.readDataReference()
                fields["ItemID"] = self.readDataReference()
                fields["Price"] = self.readVInt()
            except:
                # если не хватает байтов — просто игнор
                pass

            print(f"[DECODE] {fields}")

        except Exception as e:
            print(f"[DECODE ERROR] {e}")
            traceback.print_exc()

        return fields

    # --------------------------------
    # EXECUTE
    # --------------------------------
    def execute(self, calling_instance, fields):
        try:
            player = calling_instance.player

            if not player:
                return

            price = fields.get("Price", 0)
            currency = fields.get("CurrencyType", 0)

            # shop refresh / fake purchase
            if price <= 0:
                self.send_home_data(calling_instance)
                return

            # ---- Gems ----
            if currency == 0:
                if player.Gems >= price:
                    player.Gems -= price

            # ---- Coins ----
            elif currency == 1:
                if player.Coins >= price:
                    player.Coins -= price

            # ---- StarPoints ----
            elif currency == 2:
                if player.StarPoints >= price:
                    player.StarPoints -= price

            # можно добавить выдачу предметов тут

            self.send_home_data(calling_instance)

        except Exception as e:
            print(f"[EXECUTE ERROR] {e}")
            traceback.print_exc()

    # --------------------------------
    # САМЫЙ ВАЖНЫЙ ФИКС (OutOfSync fix)
    # --------------------------------
    def send_home_data(self, calling_instance):
        try:
            from Heart.Packets.Server.OwnHomeDataMessage import OwnHomeDataMessage

            msg = OwnHomeDataMessage(calling_instance)
            msg.encode()

            # 🔥 отправляем Message, НЕ buffer
            Messaging.send(calling_instance, msg)

            print("[HOME] OK")

        except Exception as e:
            print(f"[HOME ERROR] {e}")

    def getCommandType(self):
        return 519
