"""
首次运行时执行：python seed_data.py
将 38 个区县写入数据库（幂等：已存在则跳过）
"""
import asyncio
from sqlalchemy import select, func
from app.database import engine, Base, async_session
from app.models import District, Community, Listing, PriceHistory, CrawlBatch, CrawlTask

DISTRICTS = [
    ("两江新区", "liangjiang", True),
    ("渝中区", "yuzhong", True),
    ("南岸区", "nanan", True),
    ("九龙坡区", "jiulongpo", True),
    ("沙坪坝区", "shapingba", True),
    ("巴南区", "banan", True),
    ("大渡口区", "dadukou", True),
    ("北碚区", "beibei", True),
    ("璧山区", "bishan", True),
    ("江津区", "jiangjin", True),
    ("永川区", "yongchuan", True),
    ("合川区", "hechuan", True),
    ("长寿区", "changshou", True),
    ("涪陵区", "fuling", True),
    ("南川区", "nanchuan", True),
    ("綦江区", "qijiang", True),
    ("大足区", "dazu", True),
    ("铜梁区", "tongliang", True),
    ("潼南区", "tongnan", True),
    ("荣昌区", "rongchang", True),
    ("万州区", "wanzhou", False),
    ("开州区", "kaizhou", False),
    ("梁平区", "liangping", False),
    ("武隆区", "wulong", False),
    ("城口县", "chengkou", False),
    ("丰都县", "fengdu", False),
    ("垫江县", "dianjiang", False),
    ("忠县", "zhongxian", False),
    ("云阳县", "yunyang", False),
    ("奉节县", "fengjie", False),
    ("巫山县", "wushan", False),
    ("巫溪县", "wuxi", False),
    ("黔江区", "qianjiang", False),
    ("石柱土家族自治县", "shizhu", False),
    ("秀山土家族苗族自治县", "xiushan", False),
    ("酉阳土家族苗族自治县", "youyang", False),
    ("彭水苗族土家族自治县", "pengshui", False),
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Tables created")

    async with async_session() as session:
        # 幂等：先查已有数量
        result = await session.execute(select(func.count(District.id)))
        count = result.scalar()
        if count >= len(DISTRICTS):
            print(f"[OK] {count} districts already exist, skip")
            return

        for name, pinyin, is_urban in DISTRICTS:
            # 幂等：重名跳过
            existing = await session.execute(
                select(District.id).where(District.name == name)
            )
            if existing.scalar() is None:
                session.add(District(name=name, pinyin=pinyin, is_urban=is_urban))
        await session.commit()

    print(f"[OK] Seeded {len(DISTRICTS)} districts")


if __name__ == "__main__":
    asyncio.run(seed())
