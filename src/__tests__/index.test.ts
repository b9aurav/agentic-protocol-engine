describe('APE Core', () => {
  it('should pass basic test', () => {
    expect(1 + 1).toBe(2);
  });
  
  it('should have Node.js environment', () => {
    expect(process.env.NODE_ENV).toBeDefined();
  });
});