namespace FunctionApp.PensionFunds.Models
{
    public class PensionFund
    {
        public string FundNumber { get; set; }          // מספר
        public string FundName { get; set; }            // שם קרן
        public string CompanyName { get; set; }         // חברה מנהלת
        public string ProductType { get; set; }         // סוג מוצר (pension/insurance)
        public string FundType { get; set; }            // סוג קרן
        public decimal? AnnualReturn { get; set; }      // תשואה שנתית
        public decimal? Avg3YearReturn { get; set; }    // ממוצעת שנתית 3 שנים
        public decimal? Avg5YearReturn { get; set; }    // ממוצעת שנתית 5 שנים
        public decimal? SharpeRatio { get; set; }       // מדד שארפ
        public string? EstablishmentPeriod { get; set; } // תקופת הקמה (for insurance only)
    }
}
