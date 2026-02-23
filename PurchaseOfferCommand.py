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
            except Exception as e:
                # если не хватает байтов — просто игнор
                print(f"[DECODE] Not enough data: {e}")

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
    # ИСПРАВЛЕННЫЙ МЕТОД ОТПРАВКИ HOME DATA
    # --------------------------------
    def send_home_data(self, calling_instance):
        try:
            from Heart.Packets.Server.OwnHomeDataMessage import OwnHomeDataMessage

            msg = OwnHomeDataMessage(calling_instance)
            msg.encode()

            # ✅ Получаем закодированный буфер (обычно хранится в .buffer или .payload)
            buffer = None
            if hasattr(msg, 'buffer') and msg.buffer:
                buffer = msg.buffer
            elif hasattr(msg, 'payload') and msg.payload:
                buffer = msg.payload
            else:
                # Если неизвестно имя поля — попробуем найти первое байтовое поле
                for attr in dir(msg):
                    val = getattr(msg, attr)
                    if isinstance(val, (bytes, bytearray)) and len(val) > 0:
                        buffer = val
                        break

            if buffer is None:
                print("[HOME ERROR] Could not find encoded buffer in message")
                return

            # Отправляем буфер через Messaging
            Messaging.send(calling_instance, buffer)
            print("[HOME] OK")

        except Exception as e:
            print(f"[HOME ERROR] {e}")
            traceback.print_exc()

    def getCommandType(self):
        return 519
