#!/usr/bin/env python3
import asyncio
import re
from xhamster_api import Client

async def main():
    print("=" * 55)
    print("   XHamster - فقط لینک کیفیت‌ها (بدون دانلود)")
    print("=" * 55)

    url = input("\nلینک ویدیو را وارد کن:\n> ").strip()
    if not url:
        print("لینک خالی است!")
        return

    print("\nدر حال دریافت اطلاعات...")

    try:
        client = Client()
        video = await client.get_video(url)

        print("\n" + "=" * 55)
        print("اطلاعات ویدیو:")
        print("=" * 55)
        print(f"عنوان       : {getattr(video, 'title', 'نامشخص')}")
        print(f"حداکثر کیفیت: {getattr(video, 'max_resolution', 'نامشخص')}")

        m3u8 = getattr(video, 'm3u8_base_url', None)

        if not m3u8:
            print("\n❌ لینک m3u8 پیدا نشد.")
            return

        print(f"\nلینک اصلی m3u8:\n{m3u8}")

        qualities = re.findall(r'(\d+x\d+):(\d+p)', m3u8)

        print("\n" + "=" * 55)
        print("لینک‌های کیفیت‌های مختلف:")
        print("=" * 55)

        if qualities:
            for resolution, quality in qualities:
                quality_link = m3u8.replace("_TPL_", quality)
                print(f"\n[{quality}] → {resolution}")
                print(quality_link)
        else:
            print("\nنتوانستم کیفیت‌ها را جدا کنم. لینک اصلی را استفاده کن:")
            print(m3u8)

        print("\n" + "=" * 55)
        print("نکته: این لینک‌ها HLS (m3u8) هستند.")
        print("دانلود منیجرهایی مثل 1DM+ از m3u8 پشتیبانی می‌کنند.")
        print("=" * 55)

    except Exception as e:
        print(f"\n❌ خطا:\n{type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
