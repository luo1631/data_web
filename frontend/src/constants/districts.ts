/**
 * 重庆市 38 区县硬编码列表。
 * 与 backend/crawler/constants.py 的 DISTRICTS 和 seed_data.py 保持顺序一致。
 * 获取页面无需从数据库异步加载这些静态数据。
 */

export interface DistrictInfo {
  id: number;
  name: string;
  isUrban: boolean;
}

export const DISTRICTS: DistrictInfo[] = [
  { id: 1, name: "渝北区", isUrban: true },
  { id: 2, name: "江北区", isUrban: true },
  { id: 3, name: "渝中区", isUrban: true },
  { id: 4, name: "南岸区", isUrban: true },
  { id: 5, name: "九龙坡区", isUrban: true },
  { id: 6, name: "沙坪坝区", isUrban: true },
  { id: 7, name: "巴南区", isUrban: true },
  { id: 8, name: "大渡口区", isUrban: true },
  { id: 9, name: "北碚区", isUrban: true },
  { id: 10, name: "璧山区", isUrban: true },
  { id: 11, name: "江津区", isUrban: true },
  { id: 12, name: "永川区", isUrban: true },
  { id: 13, name: "合川区", isUrban: true },
  { id: 14, name: "长寿区", isUrban: true },
  { id: 15, name: "涪陵区", isUrban: true },
  { id: 16, name: "南川区", isUrban: true },
  { id: 17, name: "綦江区", isUrban: true },
  { id: 18, name: "大足区", isUrban: true },
  { id: 19, name: "铜梁区", isUrban: true },
  { id: 20, name: "潼南区", isUrban: true },
  { id: 21, name: "荣昌区", isUrban: true },
  { id: 22, name: "万州区", isUrban: false },
  { id: 23, name: "开州区", isUrban: false },
  { id: 24, name: "梁平区", isUrban: false },
  { id: 25, name: "武隆区", isUrban: false },
  { id: 26, name: "城口县", isUrban: false },
  { id: 27, name: "丰都县", isUrban: false },
  { id: 28, name: "垫江县", isUrban: false },
  { id: 29, name: "忠县", isUrban: false },
  { id: 30, name: "云阳县", isUrban: false },
  { id: 31, name: "奉节县", isUrban: false },
  { id: 32, name: "巫山县", isUrban: false },
  { id: 33, name: "巫溪县", isUrban: false },
  { id: 34, name: "黔江区", isUrban: false },
  { id: 35, name: "石柱土家族自治县", isUrban: false },
  { id: 36, name: "秀山土家族苗族自治县", isUrban: false },
  { id: 37, name: "酉阳土家族苗族自治县", isUrban: false },
  { id: 38, name: "彭水苗族土家族自治县", isUrban: false },
];
