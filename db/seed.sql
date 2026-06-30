-- 重庆市 38 个区县种子数据
USE cq_house;

INSERT INTO districts (id, name, pinyin, level, is_urban) VALUES
-- 主城 9 区
(1,  '渝北区', 'yubei', 1, 1),
(2,  '江北区', 'jiangbei', 1, 1),
(3,  '渝中区', 'yuzhong', 1, 1),
(4,  '南岸区', 'nanan', 1, 1),
(5,  '九龙坡区', 'jiulongpo', 1, 1),
(6,  '沙坪坝区', 'shapingba', 1, 1),
(7,  '巴南区', 'banan', 1, 1),
(8,  '大渡口区', 'dadukou', 1, 1),
(9,  '北碚区', 'beibei', 1, 1),

-- 近郊 12 区
(10, '璧山区', 'bishan', 1, 1),
(11, '江津区', 'jiangjin', 1, 1),
(12, '永川区', 'yongchuan', 1, 1),
(13, '合川区', 'hechuan', 1, 1),
(14, '长寿区', 'changshou', 1, 1),
(15, '涪陵区', 'fuling', 1, 1),
(16, '南川区', 'nanchuan', 1, 1),
(17, '綦江区', 'qijiang', 1, 1),
(18, '大足区', 'dazu', 1, 1),
(19, '铜梁区', 'tongliang', 1, 1),
(20, '潼南区', 'tongnan', 1, 1),
(21, '荣昌区', 'rongchang', 1, 1),

-- 远郊 17 区县
(22, '万州区', 'wanzhou', 1, 0),
(23, '开州区', 'kaizhou', 1, 0),
(24, '梁平区', 'liangping', 1, 0),
(25, '武隆区', 'wulong', 1, 0),
(26, '城口县', 'chengkou', 1, 0),
(27, '丰都县', 'fengdu', 1, 0),
(28, '垫江县', 'dianjiang', 1, 0),
(29, '忠县',   'zhongxian', 1, 0),
(30, '云阳县', 'yunyang', 1, 0),
(31, '奉节县', 'fengjie', 1, 0),
(32, '巫山县', 'wushan', 1, 0),
(33, '巫溪县', 'wuxi', 1, 0),
(34, '黔江区', 'qianjiang', 1, 0),
(35, '石柱土家族自治县', 'shizhu', 1, 0),
(36, '秀山土家族苗族自治县', 'xiushan', 1, 0),
(37, '酉阳土家族苗族自治县', 'youyang', 1, 0),
(38, '彭水苗族土家族自治县', 'pengshui', 1, 0);
