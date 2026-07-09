-- FinBrief default topic seed.
-- Safe to run repeatedly after schemas/supabase.sql.

insert into topics (name, normalized_name, type, source_mapping)
values
(
    'USD/KRW 환율',
    'usdkrw',
    'indicator',
    '[
      {
        "provider": "yfinance",
        "ticker": "KRW=X",
        "query": "USD/KRW 환율",
        "news_keywords": ["환율", "원달러", "달러", "USD/KRW"],
        "notes": "시연용 원달러 환율 ticker"
      },
      {
        "provider": "fred",
        "series_id": "DEXKOUS",
        "query": "USD/KRW exchange rate",
        "news_keywords": ["환율", "원달러", "달러"],
        "notes": "FRED daily exchange rate"
      }
    ]'::jsonb
),
(
    '미국 10년물 금리',
    'us_rate',
    'indicator',
    '[
      {
        "provider": "fred",
        "series_id": "DGS10",
        "query": "미국 10년물 국채금리",
        "news_keywords": ["미국 금리", "국채금리", "10년물", "연준"],
        "notes": "FRED 10-year treasury yield"
      },
      {
        "provider": "yfinance",
        "ticker": "^TNX",
        "query": "US 10-year treasury yield",
        "news_keywords": ["미국 금리", "국채금리", "10년물"],
        "notes": "Yahoo Finance treasury yield proxy"
      }
    ]'::jsonb
),
(
    '나스닥',
    'nasdaq',
    'asset',
    '[
      {
        "provider": "yfinance",
        "ticker": "^IXIC",
        "query": "나스닥 지수",
        "news_keywords": ["나스닥", "기술주", "미국 증시"],
        "notes": "NASDAQ Composite"
      }
    ]'::jsonb
),
(
    '비트코인',
    'btc',
    'asset',
    '[
      {
        "provider": "yfinance",
        "ticker": "BTC-USD",
        "query": "비트코인 가격",
        "news_keywords": ["비트코인", "가상자산", "암호화폐", "BTC"],
        "notes": "Bitcoin USD spot proxy"
      }
    ]'::jsonb
),
(
    '반도체',
    'semi',
    'sector',
    '[
      {
        "provider": "yfinance",
        "ticker": "SOXX",
        "query": "반도체 섹터",
        "news_keywords": ["반도체", "AI 반도체", "엔비디아", "메모리"],
        "notes": "Semiconductor ETF proxy"
      },
      {
        "provider": "rag",
        "query": "반도체 업황과 AI 반도체 뉴스",
        "news_keywords": ["반도체", "AI 반도체", "엔비디아", "HBM"],
        "notes": "News-only sector retrieval"
      }
    ]'::jsonb
)
on conflict (normalized_name) do update
set
    name = excluded.name,
    type = excluded.type,
    source_mapping = excluded.source_mapping,
    updated_at = now();
